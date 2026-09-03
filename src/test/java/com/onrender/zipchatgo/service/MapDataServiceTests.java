package com.onrender.zipchatgo.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import tools.jackson.databind.ObjectMapper;

class MapDataServiceTests {

    @SuppressWarnings("unchecked")
    @Test
    void searchesPropertiesWithStationNameTypeAndMaximumPrice() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "정자아파트", "아파트", 750_000_000L, "성남시 분당구 정자동"),
                property(2L, "정자고가아파트", "아파트", 900_000_000L, "성남시 분당구 정자동"),
                property(3L, "판교빌라", "빌라", 700_000_000L, "성남시 분당구 백현동")));
        MapDataService service = new MapDataService(jdbcTemplate, new ObjectMapper());

        MapDataService.PropertySearchResult result = service.searchProperties(
                "정자역", "아파트", 800_000_000L, null, 10, null);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.properties()).hasSize(1);
        assertThat(result.properties().getFirst().get("id")).isEqualTo(1L);
        assertThat(result.properties().getFirst()).doesNotContainKey("description");
    }

    @Test
    void searchesPropertiesInsideCurrentMapBounds() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "화면 안 아파트", "아파트", 750_000_000L,
                        "성남시 분당구 백현동", 37.394, 127.111),
                property(2L, "화면 밖 아파트", "아파트", 700_000_000L,
                        "성남시 분당구 정자동", 37.370, 127.111)));
        MapDataService service = new MapDataService(jdbcTemplate, new ObjectMapper());

        MapDataService.PropertySearchResult result = service.searchProperties(
                null,
                "아파트",
                800_000_000L,
                null,
                10,
                new MapDataService.GeoBounds(37.390, 127.100, 37.400, 127.120));

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.properties().getFirst().get("id")).isEqualTo(1L);
    }

    @Test
    void searchesPropertiesBySelectedLegalDongCode() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "판교동 아파트", "아파트", 750_000_000L,
                        "성남시 분당구 판교동"),
                property(2L, "삼평동 아파트", "아파트", 700_000_000L,
                        "성남시 분당구 삼평동")));
        MapDataService service = new MapDataService(jdbcTemplate, new ObjectMapper());

        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", null, "41135108", 10, null);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.properties().getFirst().get("id")).isEqualTo(1L);
    }

    @SuppressWarnings("unchecked")
    @Test
    void searchesAndMergesTransitStationEntriesByStationName() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        MapDataService service = new MapDataService(jdbcTemplate, new ObjectMapper());

        MapDataService.TransitStationSearchResult result =
                service.searchTransitStations("정자역", 5);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.stations()).hasSize(1);
        assertThat(result.stations().getFirst().get("name")).isEqualTo("정자역");
        List<String> lines = (List<String>) result.stations().getFirst().get("lines");
        assertThat(lines).contains("신분당선", "분당선");
    }

    private Map<String, Object> property(
            long id,
            String buildingName,
            String propertyType,
            long salePrice,
            String district) {
        return property(id, buildingName, propertyType, salePrice, district, 37.394, 127.111);
    }

    private Map<String, Object> property(
            long id,
            String buildingName,
            String propertyType,
            long salePrice,
            String district,
            double latitude,
            double longitude) {
        Map<String, Object> property = new LinkedHashMap<>();
        property.put("id", id);
        property.put("building_name", buildingName);
        property.put("property_type", propertyType);
        property.put("sale_price", salePrice);
        property.put("district", district);
        property.put("latitude", latitude);
        property.put("longitude", longitude);
        return property;
    }
}
