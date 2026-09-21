package com.onrender.zipchatgo.map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.LinkedHashMap;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import tools.jackson.databind.ObjectMapper;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class MapDataServiceTests {

    private JdbcTemplate jdbcTemplate;
    private MapDataService service;

    @BeforeAll
    void setUpService() {
        jdbcTemplate = mock(JdbcTemplate.class);
        service = new MapDataService(jdbcTemplate, new ObjectMapper());
    }

    @BeforeEach
    void resetJdbcTemplate() {
        reset(jdbcTemplate);
    }

    @SuppressWarnings("unchecked")
    @Test
    void searchesPropertiesWithStationNameTypeAndMaximumPrice() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "정자아파트", "아파트", 750_000_000L, "성남시 분당구 정자동"),
                property(2L, "정자고가아파트", "아파트", 900_000_000L, "성남시 분당구 정자동"),
                property(3L, "판교빌라", "빌라", 700_000_000L, "성남시 분당구 백현동")));
        MapDataService.PropertySearchResult result = service.searchProperties(
                "정자역", "아파트", 800_000_000L, null, 10, null);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.properties()).hasSize(1);
        assertThat(result.properties().getFirst().get("id")).isEqualTo(1L);
        assertThat(result.properties().getFirst()).doesNotContainKey("description");
        verify(jdbcTemplate).query(argThat((String sql) -> sql.contains("INTERVAL 12 MONTH")), any(RowMapper.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void selectedBuildingHistoryMatchesExactDongAndNameAndSortsFiveTransactions() {
        List<Map<String, Object>> rows = new java.util.ArrayList<>();
        for (int index = 0; index < 6; index++) {
            rows.add(transaction(100L + index, "효자촌(럭키)", "성남시 분당구 서현동",
                    84.90 + index * 0.01, LocalDate.of(2024, 1, 1).plusMonths(index)));
        }
        rows.add(transaction(300L, "효자촌(럭키)", "성남시 분당구 정자동",
                84.91, LocalDate.of(2025, 1, 1)));
        rows.add(transaction(301L, "효자촌(럭키)2", "성남시 분당구 서현동",
                84.91, LocalDate.of(2025, 2, 1)));
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(rows);

        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", null, null, 5, null, "contract_date", "desc",
                "selected_building_transactions", 100L, null, null);

        assertThat(result.totalCount()).isEqualTo(6);
        assertThat(result.properties()).extracting(item -> item.get("id"))
                .containsExactly(105L, 104L, 103L, 102L, 101L);
        verify(jdbcTemplate).query(argThat((String sql) -> sql.contains("INTERVAL 36 MONTH")), any(RowMapper.class));
    }

    @SuppressWarnings("unchecked")
    @Test
    void transactionAreaClassIncludesAllEightyFourSquareMeterRecords() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                transaction(1L, "효자촌(럭키)", "성남시 분당구 서현동", 84.91, LocalDate.of(2025, 1, 1)),
                transaction(2L, "효자촌(럭키)", "성남시 분당구 서현동", 84.97, LocalDate.of(2025, 2, 1)),
                transaction(3L, "효자촌(럭키)", "성남시 분당구 서현동", 84.99, LocalDate.of(2025, 3, 1)),
                transaction(4L, "효자촌(럭키)", "성남시 분당구 서현동", 85.0, LocalDate.of(2025, 4, 1))));

        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", null, null, 5, null, "contract_date", "desc",
                "selected_building_transactions", 1L, null, 84.0);

        assertThat(result.properties()).extracting(item -> item.get("id"))
                .containsExactly(3L, 2L, 1L);
    }

    @SuppressWarnings("unchecked")
    @Test
    void selectedDongTransactionHistoryUsesLegalDongCodeAndDateOrder() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                transaction(1L, "A", "성남시 분당구 정자동", 84.91, LocalDate.of(2024, 3, 1)),
                transaction(2L, "B", "성남시 분당구 수내동", 84.91, LocalDate.of(2025, 1, 1)),
                transaction(3L, "C", "성남시 분당구 정자동", 84.91, LocalDate.of(2024, 7, 1))));

        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", null, "41135103", 5, null, "contract_date", "desc",
                "transactions", null, null, null);

        assertThat(result.properties()).extracting(item -> item.get("id")).containsExactly(3L, 1L);
    }

    @SuppressWarnings("unchecked")
    @Test
    void namedBuildingHistoryRequiresExactNameAndDoesNotMixAmbiguousDongs() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                transaction(1L, "효자촌(럭키)", "성남시 분당구 서현동", 84.91, LocalDate.of(2025, 1, 1)),
                transaction(2L, "효자촌(럭키)2", "성남시 분당구 서현동", 84.91, LocalDate.of(2025, 2, 1)),
                transaction(3L, "효자촌(럭키)", "성남시 분당구 정자동", 84.91, LocalDate.of(2025, 3, 1))));

        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", null, null, 5, null, "contract_date", "desc",
                "transactions", null, "효자촌 럭키", null);

        assertThat(result.ambiguous()).isTrue();
        assertThat(result.properties()).isEmpty();

        MapDataService.PropertySearchResult resolved = service.searchProperties(
                null, "아파트", null, "41135105", 5, null, "contract_date", "desc",
                "transactions", null, "효자촌 럭키", null);
        assertThat(resolved.properties()).extracting(item -> item.get("id")).containsExactly(1L);
    }

    @SuppressWarnings("unchecked")
    @Test
    void normalPriceRankingKeepsExistingTwelveMonthScope() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "A", "아파트", 600_000_000L, "성남시 분당구 정자동"),
                property(2L, "B", "아파트", 400_000_000L, "성남시 분당구 정자동")));

        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", 700_000_000L, null, 2, null, "sale_price", "asc");

        assertThat(result.properties()).extracting(item -> item.get("id")).containsExactly(2L, 1L);
        verify(jdbcTemplate).query(argThat((String sql) -> sql.contains("INTERVAL 12 MONTH")), any(RowMapper.class));
    }

    @Test
    void searchesPropertiesInsideCurrentMapBounds() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "화면 안 아파트", "아파트", 750_000_000L,
                        "성남시 분당구 백현동", 37.394, 127.111),
                property(2L, "화면 밖 아파트", "아파트", 700_000_000L,
                        "성남시 분당구 정자동", 37.370, 127.111)));
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
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(1L, "판교동 아파트", "아파트", 750_000_000L,
                        "성남시 분당구 판교동"),
                property(2L, "삼평동 아파트", "아파트", 700_000_000L,
                        "성남시 분당구 삼평동")));
        MapDataService.PropertySearchResult result = service.searchProperties(
                null, "아파트", null, "41135108", 10, null);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.properties().getFirst().get("id")).isEqualTo(1L);
    }

    @SuppressWarnings("unchecked")
    @Test
    void getsPropertiesByIdsInRequestedOrderAndReportsMissingIds() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                property(427L, "first", "apartment", 780_000_000L, "district-a"),
                property(903L, "second", "villa", 650_000_000L, "district-b")));
        MapDataService.PropertiesByIdsResult result =
                service.getPropertiesByIds(List.of(903L, 999L, 427L));

        assertThat(result.requestedIds()).containsExactly(903L, 999L, 427L);
        assertThat(result.properties())
                .extracting(property -> property.get("id"))
                .containsExactly(903L, 427L);
        assertThat(result.missingIds()).containsExactly(999L);
        assertThat(result.properties().getFirst()).doesNotContainKey("description");
    }

    @SuppressWarnings("unchecked")
    @Test
    void searchesAndMergesTransitStationEntriesByStationName() {
        MapDataService.TransitStationSearchResult result =
                service.searchTransitStations("정자역", 5);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.stations()).hasSize(1);
        assertThat(result.stations().getFirst().get("name")).isEqualTo("정자역");
        List<String> lines = (List<String>) result.stations().getFirst().get("lines");
        assertThat(lines).contains("신분당선", "분당선");
    }

    @Test
    void searchesPoisByActualCategorySubtypeAndRegion() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                poi("H1", "정자종합병원", "의료", "종합병원", "성남시 분당구 정자동", 37.37, 127.11),
                poi("H2", "수내병원", "의료", "병원", "성남시 분당구 수내동", 37.38, 127.12),
                poi("S1", "정자초등학교", "교육", "초등학교", "성남시 분당구 정자동", 37.371, 127.111)));
        MapDataService.PoiSearchResult result = service.searchPois(
                "의료", "병원", "정자동", null, null, null, null, 5);

        assertThat(result.totalCount()).isEqualTo(1);
        assertThat(result.pois()).hasSize(1);
        assertThat(result.pois().getFirst())
                .containsEntry("id", "H1")
                .containsEntry("name", "정자종합병원")
                .containsEntry("category", "의료")
                .doesNotContainKey("distance_m");
    }

    @Test
    void searchesPoisByDistanceAndReturnsNearestFirst() {
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(List.of(
                poi("B2", "먼 정류장", "교통", "버스정류장", "성남시 분당구 정자동", 37.380, 127.110),
                poi("B1", "가까운 정류장", "교통", "버스정류장", "성남시 분당구 정자동", 37.371, 127.110)));
        MapDataService.PoiSearchResult result = service.searchPois(
                "교통", "버스정류장", null, null, 37.370, 127.110, 2_000, 1);

        assertThat(result.totalCount()).isEqualTo(2);
        assertThat(result.pois()).hasSize(1);
        assertThat(result.pois().getFirst().get("id")).isEqualTo("B1");
        assertThat((Long) result.pois().getFirst().get("distance_m")).isBetween(100L, 120L);
    }

    @SuppressWarnings("unchecked")
    @Test
    void countsAllPoisInsideSelectedLegalDongBeyondDisplayLimit() {
        List<Map<String, Object>> schools = new java.util.ArrayList<>();
        for (int index = 0; index < 12; index++) {
            schools.add(poi("S" + index, "학교 " + index, "교육", "학교",
                    "성남시 분당구 정자동", 37.370, 127.110));
        }
        schools.add(poi("OUT", "다른 동 학교", "교육", "학교",
                "성남시 분당구 정자동", 37.395, 127.110));
        when(jdbcTemplate.query(anyString(), any(RowMapper.class))).thenReturn(schools);

        MapDataService.PoiSearchResult result = service.searchPois(
                "교육", "학교", null, null, null, null, null, 10, "41135103");

        assertThat(result.totalCount()).isEqualTo(12);
        assertThat(result.pois()).hasSize(10);
        assertThat(result.pois()).extracting(item -> item.get("id")).doesNotContain("OUT");
    }

    @Test
    void searchedSubwayPoiIdExistsInMapPoiList() {
        MapDataService.PoiSearchResult result = service.searchPois(
                "교통", "지하철역", null, null, null, null, null, 1);

        assertThat(result.pois()).isNotEmpty();
        String searchedId = result.pois().getFirst().get("id").toString();
        assertThat(searchedId).startsWith("SUBWAY_");
        assertThat(service.getMapPois().data())
                .extracting(poi -> poi.get("poi_id"))
                .contains(searchedId);
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

    private Map<String, Object> transaction(
            long id, String buildingName, String district, double exclusiveArea, LocalDate contractDate) {
        Map<String, Object> row = property(id, buildingName, "아파트", 500_000_000L, district);
        row.put("exclusive_area", exclusiveArea);
        row.put("contract_date", contractDate);
        row.put("address", district + " 1");
        return row;
    }

    private Map<String, Object> poi(
            String id,
            String name,
            String category,
            String subcategory,
            String address,
            double latitude,
            double longitude) {
        Map<String, Object> poi = new LinkedHashMap<>();
        poi.put("poi_id", id);
        poi.put("name", name);
        poi.put("category", category);
        poi.put("subcategory", subcategory);
        poi.put("road_address", address);
        poi.put("province", "경기도");
        poi.put("city", "성남시");
        poi.put("town", address.substring(address.lastIndexOf(' ') + 1));
        poi.put("latitude", latitude);
        poi.put("longitude", longitude);
        return poi;
    }
}
