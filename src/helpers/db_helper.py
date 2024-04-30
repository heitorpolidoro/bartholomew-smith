"""
Database Helper Functions

This module contains helper functions for interacting with DynamoDB tables using the AWS SDK.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Generic, NoReturn, TypeVar

import boto3
from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

logger = logging.getLogger(__name__)
T = TypeVar("T")

type_map = {
    str: "S",
    int: "N",
    float: "N",
    bool: "BOOL",
    bytes: "B",
    set: {
        str: "SS",
        int: "NS",
        bytes: "BS",
    },
    list: "L",
    dict: "M",
}


class MetaBaseModelService(type):
    """
    Metaclass for BaseModelService classes.

    This metaclass manages table and resource access for the service class.
    """

    def __init__(cls: type["BaseModelService"], *args) -> NoReturn:
        super().__init__(*args)
        cls._resource = None
        cls._table = None

    @property
    def table(cls: type["BaseModelService"]) -> ServiceResource:
        """
        Returns the DynamoDB table associated with the service class.

        If the table doesn't exist, it attempts to create it.
        """
        if cls._table is None:
            cls._table = cls.get_table()
        return cls._table

    @property
    def resource(cls: type["BaseModelService"]) -> boto3.resource:
        """Returns the DynamoDB resource client."""
        if cls._resource is None:
            cls._resource = boto3.resource("dynamodb", region_name="us-east-1")
        return cls._resource

    @property
    def table_name(cls: type["BaseModelService"]) -> str:
        """
        Returns the name of the DynamoDB table associated with the service class.

        The table name is derived from the class name in lowercase.
        """
        return cls.clazz.__name__.lower()

    @property
    def clazz(cls: type["BaseModelService"]) -> type["BaseModel"]:
        """
        Returns the Pydantic model class associated with the service class.

        This is retrieved from the first type argument of the service class's base class.
        """
        return cls.__orig_bases__[0].__args__[0]


class BaseModelService(Generic[T], metaclass=MetaBaseModelService):
    """
    This class defines a base model service that other model services can inherit
    from. It provides common functionality for retrieving, creating, updating and
    deleting models from the database.
    """

    _table = None
    _resource = None

    @classmethod
    def get_table(cls) -> ServiceResource:
        """
        Returns the DynamoDB table associated with the service class.

        If the table doesn't exist, it attempts to create it.
        """
        try:
            table = BaseModelService.resource.Table(cls.table_name)
            if not table.creation_date_time:
                raise AssertionError("Table doesn't exist")
        except ClientError as err:
            # This will not result in a failed assertion
            if err.response["Error"]["Code"] == "ResourceNotFoundException":
                return cls.create_table()
            raise
        return table

    @classmethod
    def all(cls) -> list["BaseModel"]:
        """Return all models from the table."""
        return cls.filter()

    @classmethod
    def filter(cls, **kwargs) -> list[T]:
        """Return all models from the table matching the filter."""
        try:
            scan_attributes = {}
            if kwargs:
                filter_expression = []
                expression_attribute_values = {}
                for attr_name, attr_value in kwargs.items():
                    filter_expression.append(f"{attr_name}=:{attr_name}")
                    if isinstance(attr_value, Enum):
                        attr_value = attr_value.value
                    expression_attribute_values[f":{attr_name}"] = attr_value
                scan_attributes = {
                    "FilterExpression": " and ".join(filter_expression),
                    "ExpressionAttributeValues": expression_attribute_values,
                }
            response = cls.table.scan(**scan_attributes)
        except ClientError as err:
            logger.error(
                "Couldn't get any movie from table %s. Here's why: %s: %s",
                cls.table.name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise
        return [
            cls.clazz(**item)
            for item in sorted(response["Items"], key=lambda item: item["created_at"])
        ]

    @classmethod
    def create_table(cls) -> ServiceResource:
        """Creates a DynamoDB table"""
        try:
            key_schema = cls.clazz.key_schema
            if not key_schema:
                raise AssertionError("Key schema doesn't exist")
            dy_key_schema = []
            attribute_definitions = []
            for attr_name in key_schema:
                dy_key_schema.append(
                    {
                        "AttributeName": attr_name,
                        "KeyType": "HASH" if attr_name == key_schema[0] else "RANGE",
                    }
                )
                attr = cls.clazz.model_fields[attr_name]
                python_type = attr.annotation
                if hasattr(python_type, "__args__"):
                    python_type = python_type.__args__[0]
                elif issubclass(python_type, Enum):
                    python_type = str
                attribute_definitions.append(
                    {"AttributeName": attr_name, "AttributeType": type_map[python_type]}
                )
            table = cls.resource.create_table(
                TableName=cls.table_name,
                KeySchema=dy_key_schema,
                AttributeDefinitions=attribute_definitions,
                ProvisionedThroughput={
                    "ReadCapacityUnits": 10,
                    "WriteCapacityUnits": 10,
                },
            )
            table.wait_until_exists()
        except ClientError as err:
            logger.error(
                "Couldn't create table %s. Here's why: %s: %s",
                cls.table_name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise
        return table

    @classmethod
    def insert_one(cls, item: T) -> T:
        """Insert one item in the table"""
        cls.table.put_item(Item=item.dynamo_dict())
        return item

    @classmethod
    def insert_many(cls, items: list["BaseModel"]) -> NoReturn:
        """Insert a list of items in the table"""
        with cls.table.batch_writer() as writer:
            for item in items:
                writer.put_item(Item=item.dynamo_dict())

    @classmethod
    def update(cls, item: "BaseModel", **kwargs) -> NoReturn:
        """Update an item in the table"""
        dy_key = {}
        key_schema = cls.clazz.key_schema
        attribute_values = kwargs or item.dynamo_dict()
        for attr in key_schema:
            dy_key[attr] = getattr(item, attr)
            attribute_values.pop(attr, None)
        update_expression = []
        expression_attribute_values = {}
        for attr_name, attr_value in attribute_values.items():
            setattr(item, attr_name, attr_value)
            update_expression.append(f"{attr_name}=:{attr_name}")
            if isinstance(attr_value, Enum):
                attr_value = attr_value.value
            expression_attribute_values[f":{attr_name}"] = attr_value
        cls.table.update_item(
            Key=dy_key,
            UpdateExpression="set " + ",".join(update_expression),
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW",
        )


class BaseModel(PydanticBaseModel):
    """
    The BaseModel class acts as a base class for all other model classes.
    Any model class that needs to interact with the database should inherit from this class.
    """

    key_schema: ClassVar[list[str]] = None

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dynamo_dict(self) -> dict[str, Any]:
        """Returns a dict that dynamo will understand"""
        return {
            k: v.value if isinstance(v, Enum) else v
            for k, v in self.model_dump().items()
        }

    def __hash__(self) -> int:
        """Return the hash of this item"""
        key_schema = self.key_schema
        hash_dict = {}
        for attr in key_schema:
            hash_dict[attr] = getattr(self, attr)
        return hash(str(hash_dict))
