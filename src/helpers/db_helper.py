import logging
import os
from datetime import datetime
from enum import Enum
from typing import Generic, Iterable, Optional, TypeVar

import boto3
from boto3.dynamodb.conditions import Key
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
    def __init__(cls, *args):
        super().__init__(*args)

    @property
    def table(self):
        if self._table is None:
            self._table = self.get_table()
        return self._table

    @property
    def resource(self):
        if self._resource is None:
            self._resource = boto3.resource("dynamodb", region_name="us-east-1")
        return self._resource

    @property
    def table_name(self):
        return self.clazz.__name__.lower()

    @property
    def clazz(self):
        return self.__orig_bases__[0].__args__[0]


class BaseModelService(Generic[T], metaclass=MetaBaseModelService):
    _table = None
    _resource = None

    @classmethod
    def get_table(cls):
        try:
            table = BaseModelService.resource.Table(cls.table_name)
            assert table.creation_date_time
        except ClientError as err:
            # This will not result in a failed assertion
            if err.response["Error"]["Code"] == "ResourceNotFoundException":
                return cls.create_table()
            raise
        else:
            return table

    @classmethod
    def all(cls):
        return cls.filter()

    @classmethod
    def filter(cls, **kwargs):
        try:
            scan_attributes = {}
            if kwargs:
                filter_expression = []
                expression_attribute_values = {}
                for attr_name, attr_value in kwargs.items():
                    filter_expression.append(f"{attr_name}=:{attr_name}")
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
        else:
            return [
                cls.clazz(**item)
                for item in sorted(
                    response["Items"], key=lambda item: item["created_at"]
                )
            ]

    @classmethod
    def create_table(cls):
        try:
            key_schema = cls.clazz.Config.key_schema
            assert key_schema
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
        else:
            return table

    @classmethod
    def insert_many(cls, items):
        with cls.table.batch_writer() as writer:
            for item in items:
                writer.put_item(Item=item.dynamo_dict())

    @classmethod
    def update(cls, item):
        dy_key = {}
        key_schema = cls.clazz.Config.key_schema
        attribute_values = item.dynamo_dict()
        for attr in key_schema:
            dy_key[attr] = getattr(item, attr)
            attribute_values.pop(attr)
        update_expression = []
        expression_attribute_values = {}
        for attr_name, attr_value in attribute_values.items():
            update_expression.append(f"{attr_name}=:{attr_name}")
            expression_attribute_values[f":{attr_name}"] = attr_value
        cls.table.update_item(
            Key=dy_key,
            UpdateExpression="set " + ",".join(update_expression),
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="UPDATED_NEW",
        )


class BaseModel(PydanticBaseModel):
    class Config:
        key_schema = None

    def dynamo_dict(self):
        return {
            k: v.value if isinstance(v, Enum) else v
            for k, v in self.dict().items()
            if v is not None
        }

    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
