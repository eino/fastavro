import fastavro
from fastavro.__main__ import _clean_json_record
import pytest

from decimal import Decimal
from io import BytesIO
from uuid import uuid4
import datetime
import sys
import os

from .conftest import assert_naive_datetime_equal_to_tz_datetime


schema = {
    "fields": [
        {
            "name": "date",
            "type": {'type': 'int', 'logicalType': 'date'}
        },
        {
            "name": "timestamp-millis",
            "type": {'type': 'long', 'logicalType': 'timestamp-millis'}
        },
        {
            "name": "timestamp-micros",
            "type": {'type': 'long', 'logicalType': 'timestamp-micros'}
        },
        {
            "name": "uuid",
            "type": {'type': 'string', 'logicalType': 'uuid'}
        },
        {
            "name": "time-millis",
            "type": {'type': 'int', 'logicalType': 'time-millis'}
        },
        {
            "name": "time-micros",
            "type": {'type': 'long', 'logicalType': 'time-micros'}
        }
    ],
    "namespace": "namespace",
    "name": "name",
    "type": "record"
}


def serialize(schema, data):
    bytes_writer = BytesIO()
    fastavro.schemaless_writer(bytes_writer, schema, data)
    return bytes_writer.getvalue()


def deserialize(schema, binary):
    bytes_writer = BytesIO()
    bytes_writer.write(binary)
    bytes_writer.seek(0)

    res = fastavro.schemaless_reader(bytes_writer, schema)
    return res


def test_logical_types():
    data1 = {
        'date': datetime.date.today(),
        'timestamp-millis': datetime.datetime.now(),
        'timestamp-micros': datetime.datetime.now(),
        'uuid': uuid4(),
        'time-millis': datetime.datetime.now().time(),
        'time-micros': datetime.datetime.now().time(),

    }
    binary = serialize(schema, data1)
    data2 = deserialize(schema, binary)
    assert (data1['date'] == data2['date'])
    assert_naive_datetime_equal_to_tz_datetime(
        data1['timestamp-micros'],
        data2['timestamp-micros'],
    )
    assert (int(data1['timestamp-millis'].microsecond / 1000) * 1000
            == data2['timestamp-millis'].microsecond)
    assert (int(data1['time-millis'].microsecond / 1000) * 1000
            == data2['time-millis'].microsecond)


@pytest.mark.skipif(os.name == 'nt' and sys.version_info[:2] == (3, 6),
                    reason='Python Bug: https://bugs.python.org/issue29097')
def test_not_logical_ints():
    data1 = {
        'date': 1,
        'timestamp-millis': 2,
        'timestamp-micros': 3,
        'uuid': uuid4(),
        'time-millis': 4,
        'time-micros': 5,

    }
    binary = serialize(schema, data1)
    data2 = deserialize(schema, binary)
    # 1 day since 1970-1-1
    assert (data2['date'] == datetime.date(1970, 1, 2))


schema_null = {
    "fields": [
        {
            "name": "date",
            "type": ["null", {'type': 'int', 'logicalType': 'date'}]
        },
    ],
    "namespace": "namespace",
    "name": "name",
    "type": "record"
}


def test_null():
    data1 = {
        # 'date': None,
    }
    binary = serialize(schema_null, data1)
    data2 = deserialize(schema_null, binary)
    assert (data2['date'] is None)


def test_not_null_datetime():
    data1 = {'date': datetime.datetime(2017, 1, 1)}
    binary = serialize(schema_null, data1)
    data2 = deserialize(schema_null, binary)
    assert (data2['date'] == datetime.date(2017, 1, 1))


def test_not_null_date():
    data1 = {'date': datetime.date(2017, 1, 1)}
    binary = serialize(schema_null, data1)
    data2 = deserialize(schema_null, binary)
    assert (data2['date'] == datetime.date(2017, 1, 1))


# particularly critical on Windows
# see https://github.com/fastavro/fastavro/issues/389
@pytest.mark.skipif(
    os.name == "nt" and sys.version_info <= (3, 0),
    reason="Bug was not fixed on Python 2"
)
def test_ancient_datetime():
    schema_datetime = {
        "fields": [
            {
                "name": "timestamp-millis",
                "type": {'type': 'long', 'logicalType': 'timestamp-millis'}
            },
            {
                "name": "timestamp-micros",
                "type": {'type': 'long', 'logicalType': 'timestamp-micros'}
            }
        ],
        "namespace": "namespace",
        "name": "name",
        "type": "record"
    }

    data1 = {
        'timestamp-millis': datetime.datetime(1960, 1, 1),
        'timestamp-micros': datetime.datetime(1960, 1, 1)
    }
    binary = serialize(schema_datetime, data1)
    data2 = deserialize(schema_datetime, binary)

    assert data1['timestamp-millis'] == data2['timestamp-millis'].replace(
        tzinfo=None)
    assert data1['timestamp-micros'] == data2['timestamp-micros'].replace(
        tzinfo=None)


# test bytes decimal
schema_bytes_decimal = {
    "name": "n",
    "namespace": "namespace",
    "type": "bytes",
    "logicalType": "decimal",
    "precision": 20,
    "scale": 3,
}


@pytest.mark.parametrize(
    'input_data, expected_binary',
    [
        (Decimal("0.0"), b'\x02\x00'),
        (Decimal("-0.0"), b'\x02\x00'),
        (Decimal("0.1"), b'\x02d'),
        (Decimal("-0.1"), b'\x02\x9c'),
        (Decimal("0.2"), b'\x04\x00\xc8'),
        (Decimal("-0.2"), b'\x04\xff8'),
        (Decimal("0.456"), b'\x04\x01\xc8'),
        (Decimal("-0.456"), b'\x04\xfe8'),
        (Decimal("2.55"), b'\x04\t\xf6'),
        (Decimal("-2.55"), b'\x04\xf6\n'),
        (Decimal("2.90"), b'\x04\x0bT'),
        (Decimal("-2.90"), b'\x04\xf4\xac'),
        (Decimal("123.456"), b'\x06\x01\xe2@'),
        (Decimal("-123.456"), b'\x06\xfe\x1d\xc0'),
        (Decimal("3245.234"), b'\x061\x84\xb2'),
        (Decimal("-3245.234"), b'\x06\xce{N'),
        (
            Decimal("9999999999999999.456"),
            b'\x12\x00\x8a\xc7#\x04\x89\xe7\xfd\xe0'
        ),
        (Decimal("-999999999999999.456"), b'\x10\xf2\x1fILX\x9c\x02 '),
    ]
)
def test_bytes_decimal(input_data, expected_binary):
    binary = serialize(schema_bytes_decimal, input_data)
    assert (binary == expected_binary)
    output_data = deserialize(schema_bytes_decimal, binary)
    assert (input_data == output_data)


def test_bytes_decimal_scale():
    data1 = Decimal("123.456678")  # does not fit scale
    with pytest.raises(ValueError):
        serialize(schema_bytes_decimal, data1)


schema_bytes_decimal_leftmost = {
    "name": "n",
    "namespace": "namespace",
    "type": "bytes",
    "logicalType": "decimal",
    "precision": 18,
    "scale": 6,
}


def test_bytes_decimal_leftmost():
    binary = serialize(schema_bytes_decimal_leftmost, b'\xd5F\x80')
    data2 = deserialize(schema_bytes_decimal_leftmost, binary)
    assert (Decimal("-2.80") == data2)


# test fixed decimal
schema_fixed_decimal = {
    "name": "n",
    "namespace": "namespace",
    "type": "fixed",
    "size": 8,
    "logicalType": "decimal",
    "precision": 15,
    "scale": 3,
}


def test_fixed_decimal_negative():
    data1 = Decimal("-2.90")
    binary = serialize(schema_fixed_decimal, data1)
    data2 = deserialize(schema_fixed_decimal, binary)
    assert (data1 == data2)
    assert (len(binary) == schema_fixed_decimal['size'])


def test_fixed_decimal_zero():
    data1 = Decimal("0.0")
    binary = serialize(schema_fixed_decimal, data1)
    data2 = deserialize(schema_fixed_decimal, binary)
    assert (data1 == data2)
    assert (len(binary) == schema_fixed_decimal['size'])


def test_fixed_decimal_positive():
    data1 = Decimal("123.456")
    binary = serialize(schema_fixed_decimal, data1)
    data2 = deserialize(schema_fixed_decimal, binary)
    assert (data1 == data2)
    assert (len(binary) == schema_fixed_decimal['size'])


def test_fixed_decimal_scale():
    data1 = Decimal("123.456678")  # does not fit scale
    with pytest.raises(ValueError):
        serialize(schema_fixed_decimal, data1)


schema_fixed_decimal_leftmost = {
    "name": "n",
    "namespace": "namespace",
    "type": "fixed",
    "size": 8,
    "logicalType": "decimal",
    "precision": 18,
    "scale": 6,
}


def test_fixed_decimal_binary():
    binary = serialize(schema_fixed_decimal_leftmost,
                       b'\xFF\xFF\xFF\xFF\xFF\xd5F\x80')
    data2 = deserialize(schema_fixed_decimal_leftmost, binary)
    assert (Decimal("-2.80") == data2)


def test_clean_json_list():
    values = [
        datetime.datetime.now(),
        datetime.date.today(),
        uuid4(),
        Decimal('1.23'),
    ]
    str_values = [
        values[0].isoformat(),
        values[1].isoformat(),
        str(values[2]),
        str(values[3]),
    ]
    _clean_json_record(values)
    assert values == str_values


def test_clean_json_dict():
    values = {
        '1': datetime.datetime.now(),
        '2': datetime.date.today(),
        '3': uuid4(),
        '4': Decimal('1.23'),
    }
    str_values = {
        '1': values['1'].isoformat(),
        '2': values['2'].isoformat(),
        '3': str(values['3']),
        '4': str(values['4']),
    }
    _clean_json_record(values)
    assert values == str_values


def test_unknown_logical_type():
    unknown_type_schema = {
        "type": "record",
        "name": "t_customers",
        "fields": [{
            "name": "name",
            "type": {
                "type": "string",
                "logicalType": "varchar",
                "maxLength": 200
            },
        }, {
            "name": "address",
            "type": {
                "type": "record",
                "name": "t_address",
                "fields": [{
                    "name": "street",
                    "type": {
                        "type": "string",
                        "logicalType": "varchar",
                        "maxLength": 240
                    }
                }, {
                    "name": "city",
                    "type": {
                        "type": "string",
                        "logicalType": "varchar",
                        "maxLength": 80
                    }
                }, {
                    "name": "zip",
                    "type": {
                        "type": "string",
                        "logicalType": "varchar",
                        "maxLength": 18
                    }
                }]
            }
        }]
    }

    data1 = {
        'name': 'foo',
        'address': {
            'street': '123 street',
            'city': 'city',
            'zip': '00000'
        }
    }
    converted = serialize(unknown_type_schema, data1)
    data2 = deserialize(unknown_type_schema, converted)
    assert (data1 == data2)


def test_default_scale_value():
    schema = {
        "name": "test_default_scale_value",
        "type": "fixed",
        "size": 8,
        "logicalType": "decimal",
        "precision": 15,
    }

    data1 = Decimal("-2")
    binary = serialize(schema, data1)
    data2 = deserialize(schema, binary)
    assert (data1 == data2)


def test_date_as_string():
    schema = {
        "name": "test_date_as_string",
        "type": "int",
        "logicalType": "date",
    }

    data1 = "2019-05-06"
    binary = serialize(schema, data1)
    data2 = deserialize(schema, binary)
    assert (datetime.date(2019, 5, 6) == data2)


@pytest.mark.skipif(
    hasattr(sys, 'pypy_version_info'),
    reason='pandas takes forever to install on pypy'
)
def test_pandas_datetime():
    """https://github.com/gojek/feast/pull/490#issuecomment-590623525"""

    # Import here as pandas is not installed on pypy for testing
    import pandas as pd
    import pytz

    schema = {
        "fields": [
            {
                "name": "timestamp-micros",
                "type": [
                    "null", {'type': 'long', 'logicalType': 'timestamp-micros'}
                ]
            }
        ],
        "name": "test_pandas_datetime",
        "type": "record",
    }

    data1 = {
        "timestamp-micros": pd.to_datetime(
            datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        )
    }
    assert serialize(schema, data1)
