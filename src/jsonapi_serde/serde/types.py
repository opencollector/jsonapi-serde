import typing

JSONScalar = typing.Union[bool, int, float, str]
JSONArray = typing.Sequence[typing.Any]
MutableJSONArray = typing.MutableSequence[typing.Any]
JSONObject = typing.Mapping[str, typing.Any]
MutableJSONObject = typing.MutableMapping[str, typing.Any]
JSONValue = typing.Union[JSONScalar, JSONArray, JSONObject, None]
