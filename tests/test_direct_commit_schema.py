from app.schemas.commit import DirectEntityItem


def test_direct_entity_item_accepts_alias_temp_insert_key():
    item = DirectEntityItem.model_validate(
        {
            "entity_type": "LINE",
            "geom_wkt": "LINESTRING(0 0,1 1)",
            "_temp_insert_key": 123,
        }
    )
    assert item.temp_insert_key == 123


def test_direct_entity_item_dump_by_alias_keeps_temp_insert_key():
    item = DirectEntityItem(
        entity_type="LINE",
        geom_wkt="LINESTRING(0 0,1 1)",
        temp_insert_key=77,
    )
    dumped = item.model_dump(by_alias=True)
    assert dumped.get("_temp_insert_key") == 77
    assert "temp_insert_key" not in dumped


def test_direct_entity_item_accepts_field_name_temp_insert_key():
    item = DirectEntityItem.model_validate(
        {
            "entity_type": "LINE",
            "geom_wkt": "LINESTRING(0 0,1 1)",
            "temp_insert_key": "45",
        }
    )
    assert item.temp_insert_key == 45
