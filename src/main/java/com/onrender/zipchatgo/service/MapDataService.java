package com.onrender.zipchatgo.service;

import java.io.IOException;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ClassPathResource;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

@Service
public class MapDataService {

    private static final Logger log = LoggerFactory.getLogger(MapDataService.class);
    private static final String PROPERTIES_RESOURCE = "static/data/properties.json";
    private static final String POIS_RESOURCE = "static/data/poi_database.json";
    private static final String TRANSIT_POINTS_RESOURCE = "static/data/transit_points_bundang.json";
    private static final List<String> PROPERTY_SEARCH_FIELDS = List.of(
            "title", "description", "building_name", "address", "district", "lot_number");
    private static final List<String> PROPERTY_SUMMARY_FIELDS = List.of(
            "id", "title", "building_name", "property_type", "sale_price", "deposit",
            "monthly_rent", "maintenance_fee", "exclusive_area", "floor", "built_year",
            "address", "district", "latitude", "longitude", "contract_date");
    private static final Map<String, String> BUNDANG_LEGAL_DONG_NAMES = Map.ofEntries(
            Map.entry("41135101", "분당동"),
            Map.entry("41135102", "수내동"),
            Map.entry("41135103", "정자동"),
            Map.entry("41135104", "율동"),
            Map.entry("41135105", "서현동"),
            Map.entry("41135106", "이매동"),
            Map.entry("41135107", "야탑동"),
            Map.entry("41135108", "판교동"),
            Map.entry("41135109", "삼평동"),
            Map.entry("41135110", "백현동"),
            Map.entry("41135111", "금곡동"),
            Map.entry("41135112", "궁내동"),
            Map.entry("41135113", "동원동"),
            Map.entry("41135114", "구미동"),
            Map.entry("41135115", "운중동"),
            Map.entry("41135116", "대장동"),
            Map.entry("41135117", "석운동"),
            Map.entry("41135118", "하산운동"));

    private static final String PROPERTIES_SQL = """
            SELECT id, title, description, building_name, property_type,
                   sale_price, deposit, monthly_rent, maintenance_fee,
                   exclusive_area, floor, built_year, address, district,
                   lot_number, latitude, longitude, thumbnail_url,
                   contract_date, created_at, updated_at
              FROM properties
             WHERE contract_date >= DATE_SUB(
                       DATE_FORMAT(CURRENT_DATE(), '%Y-%m-01'), INTERVAL 12 MONTH
                   )
               AND contract_date < DATE_ADD(
                       LAST_DAY(CURRENT_DATE()), INTERVAL 1 DAY
                   )
             ORDER BY id
            """;

    private static final String POIS_SQL = """
            SELECT poi_id, source_type, name, category, subcategory,
                   road_address, province, city, town, latitude, longitude,
                   bus_routes, business_status, representative_name,
                   registration_number
              FROM poi
             ORDER BY poi_id
            """;

    private static final String PRICE_HISTORY_SQL = """
            SELECT DATE_FORMAT(p.contract_date, '%Y-%m') AS month,
                   ROUND(AVG(p.sale_price)) AS average_price,
                   COUNT(*) AS trade_count
              FROM properties p
              JOIN properties selected ON selected.id = ?
             WHERE p.sale_price > 0
               AND p.contract_date >= ?
               AND p.contract_date < DATE_ADD(LAST_DAY(CURRENT_DATE()), INTERVAL 1 DAY)
               AND ROUND(p.exclusive_area / 3.3058) = ROUND(selected.exclusive_area / 3.3058)
               AND (
                    (TRIM(COALESCE(selected.building_name, '')) <> ''
                     AND TRIM(COALESCE(selected.address, '')) <> ''
                     AND TRIM(COALESCE(p.building_name, '')) = TRIM(selected.building_name)
                     AND TRIM(COALESCE(p.address, '')) = TRIM(selected.address))
                 OR (TRIM(COALESCE(selected.building_name, '')) <> ''
                     AND TRIM(COALESCE(selected.address, '')) = ''
                     AND TRIM(COALESCE(p.building_name, '')) = TRIM(selected.building_name))
                 OR (TRIM(COALESCE(selected.building_name, '')) = ''
                     AND TRIM(COALESCE(selected.address, '')) <> ''
                     AND TRIM(COALESCE(p.address, '')) = TRIM(selected.address))
               )
             GROUP BY DATE_FORMAT(p.contract_date, '%Y-%m')
             ORDER BY month
            """;

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;
    private final List<Map<String, Object>> fallbackProperties;
    private final List<Map<String, Object>> fallbackPois;
    private final List<Map<String, Object>> transitStations;

    public MapDataService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.fallbackProperties = readFallback(PROPERTIES_RESOURCE);
        this.fallbackPois = readFallback(POIS_RESOURCE);
        this.transitStations = readTransitStations();
    }

    public MapDataResult getProperties() {
        return queryOrFallback("properties", PROPERTIES_SQL, fallbackProperties);
    }

    public MapDataResult getPois() {
        return queryOrFallback("poi", POIS_SQL, fallbackPois);
    }

    public PropertySearchResult searchProperties(
            String keyword,
            String propertyType,
            Long maxPrice,
            String legalDongCode,
            int limit,
            GeoBounds bounds) {
        MapDataResult allProperties = getProperties();
        String normalizedKeyword = normalize(keyword);
        String stationKeyword = normalizedKeyword.endsWith("역") && normalizedKeyword.length() > 1
                ? normalizedKeyword.substring(0, normalizedKeyword.length() - 1)
                : normalizedKeyword;
        String normalizedType = normalize(propertyType);
        String normalizedLegalDongCode = normalize(legalDongCode);
        String legalDongName = BUNDANG_LEGAL_DONG_NAMES.get(normalizedLegalDongCode);

        List<Map<String, Object>> matches = allProperties.data().stream()
                .filter(property -> matchesKeyword(property, normalizedKeyword, stationKeyword))
                .filter(property -> normalizedLegalDongCode.isEmpty()
                        || legalDongName != null && matchesLegalDong(property, legalDongName))
                .filter(property -> normalizedType.isEmpty()
                        || normalizedType.equals(normalize(property.get("property_type"))))
                .filter(property -> maxPrice == null || priceOf(property) <= maxPrice)
                .filter(property -> bounds == null || bounds.contains(
                        coordinateOf(property, "latitude"),
                        coordinateOf(property, "longitude")))
                .toList();

        List<Map<String, Object>> summaries = matches.stream()
                .limit(limit)
                .map(this::summarizeProperty)
                .toList();

        return new PropertySearchResult(summaries, matches.size(), allProperties.source());
    }

    private boolean matchesLegalDong(Map<String, Object> property, String legalDongName) {
        return PROPERTY_SEARCH_FIELDS.stream()
                .map(property::get)
                .map(this::normalize)
                .anyMatch(value -> value.contains(legalDongName));
    }

    public TransitStationSearchResult searchTransitStations(String query, int limit) {
        String normalizedQuery = normalizeStationName(query);
        if (normalizedQuery.isEmpty()) {
            return new TransitStationSearchResult(List.of(), 0);
        }

        Map<String, List<Map<String, Object>>> grouped = new LinkedHashMap<>();
        for (Map<String, Object> station : transitStations) {
            String normalizedName = normalizeStationName(station.get("name"));
            if (normalizedName.contains(normalizedQuery)) {
                grouped.computeIfAbsent(normalizedName, ignored -> new ArrayList<>()).add(station);
            }
        }

        List<Map<String, Object>> stations = grouped.entrySet().stream()
                .limit(limit)
                .map(entry -> summarizeStation(entry.getKey(), entry.getValue()))
                .toList();
        return new TransitStationSearchResult(stations, grouped.size());
    }

    public List<Map<String, Object>> getPriceHistory(long propertyId, int requestedYears) {
        int years = requestedYears == 1 ? 1 : 3;
        LocalDate startDate = LocalDate.now().minusYears(years).withDayOfMonth(1);

        return jdbcTemplate.queryForList(PRICE_HISTORY_SQL, propertyId, startDate);
    }

    private MapDataResult queryOrFallback(
            String dataName,
            String sql,
            List<Map<String, Object>> fallbackData) {
        try {
            List<Map<String, Object>> data = jdbcTemplate.query(sql, this::mapRow);
            log.info("TiDB {} 데이터 {}건을 조회했습니다.", dataName, data.size());
            return new MapDataResult(data, MapDataSource.TIDB);
        } catch (DataAccessException exception) {
            log.error(
                    "TiDB {} 데이터 조회에 실패해 샘플 JSON {}건을 사용합니다.",
                    dataName,
                    fallbackData.size(),
                    exception);
            return new MapDataResult(fallbackData, MapDataSource.FALLBACK_JSON);
        }
    }

    private Map<String, Object> mapRow(ResultSet resultSet, int rowNumber) throws SQLException {
        ResultSetMetaData metadata = resultSet.getMetaData();
        Map<String, Object> row = new LinkedHashMap<>();

        for (int column = 1; column <= metadata.getColumnCount(); column++) {
            String name = metadata.getColumnLabel(column);
            Object value = resultSet.getObject(column);

            if ("bus_routes".equals(name) && value instanceof String json && !json.isBlank()) {
                value = parseJsonValue(json);
            }
            row.put(name, value);
        }

        return row;
    }

    private Object parseJsonValue(String json) throws SQLException {
        try {
            return objectMapper.readValue(json, Object.class);
        } catch (RuntimeException exception) {
            throw new SQLException("poi.bus_routes JSON을 읽을 수 없습니다.", exception);
        }
    }

    private boolean matchesKeyword(
            Map<String, Object> property,
            String keyword,
            String stationKeyword) {
        if (keyword.isEmpty()) {
            return true;
        }

        StringBuilder searchText = new StringBuilder();
        for (String field : PROPERTY_SEARCH_FIELDS) {
            searchText.append(' ').append(normalize(property.get(field)));
        }

        String text = searchText.toString();
        return text.contains(keyword)
                || (!stationKeyword.equals(keyword) && text.contains(stationKeyword));
    }

    private long priceOf(Map<String, Object> property) {
        Object value = property.get("sale_price");
        return value instanceof Number number ? number.longValue() : Long.MAX_VALUE;
    }

    private double coordinateOf(Map<String, Object> property, String field) {
        Object value = property.get(field);
        return value instanceof Number number ? number.doubleValue() : Double.NaN;
    }

    private Map<String, Object> summarizeStation(
            String normalizedName,
            List<Map<String, Object>> sameStationEntries) {
        double latitude = sameStationEntries.stream()
                .mapToDouble(item -> coordinateOf(item, "lat"))
                .filter(Double::isFinite)
                .average()
                .orElse(Double.NaN);
        double longitude = sameStationEntries.stream()
                .mapToDouble(item -> coordinateOf(item, "lng"))
                .filter(Double::isFinite)
                .average()
                .orElse(Double.NaN);
        List<String> lines = sameStationEntries.stream()
                .map(item -> normalize(item.get("line")))
                .filter(line -> !line.isEmpty())
                .distinct()
                .toList();

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("name", normalizedName + "역");
        summary.put("lines", lines);
        summary.put("latitude", latitude);
        summary.put("longitude", longitude);
        return summary;
    }

    private String normalizeStationName(Object value) {
        String name = normalize(value).replaceAll("\\s+", "");
        int parenthesisIndex = name.indexOf('(');
        if (parenthesisIndex >= 0) {
            name = name.substring(0, parenthesisIndex);
        }
        return name.endsWith("역") && name.length() > 1
                ? name.substring(0, name.length() - 1)
                : name;
    }

    private Map<String, Object> summarizeProperty(Map<String, Object> property) {
        Map<String, Object> summary = new LinkedHashMap<>();
        for (String field : PROPERTY_SUMMARY_FIELDS) {
            summary.put(field, property.get(field));
        }
        return summary;
    }

    private String normalize(Object value) {
        return value == null ? "" : value.toString().trim().toLowerCase(Locale.ROOT);
    }

    private List<Map<String, Object>> readFallback(String path) {
        try {
            return objectMapper.readValue(
                    new ClassPathResource(path).getInputStream(),
                    new TypeReference<ArrayList<Map<String, Object>>>() {});
        } catch (IOException exception) {
            throw new IllegalStateException("지도 샘플 데이터 파일을 읽을 수 없습니다: " + path, exception);
        }
    }

    public record MapDataResult(List<Map<String, Object>> data, MapDataSource source) {}

    public record PropertySearchResult(
            List<Map<String, Object>> properties,
            int totalCount,
            MapDataSource source) {}

    public record TransitStationSearchResult(
            List<Map<String, Object>> stations,
            int totalCount) {}

    public record GeoBounds(double south, double west, double north, double east) {
        public boolean contains(double latitude, double longitude) {
            return Double.isFinite(latitude)
                    && Double.isFinite(longitude)
                    && latitude >= south
                    && latitude <= north
                    && longitude >= west
                    && longitude <= east;
        }
    }

    private List<Map<String, Object>> readTransitStations() {
        try {
            Map<String, List<Map<String, Object>>> data = objectMapper.readValue(
                    new ClassPathResource(TRANSIT_POINTS_RESOURCE).getInputStream(),
                    new TypeReference<LinkedHashMap<String, List<Map<String, Object>>>>() {});
            return data.getOrDefault("subway", List.of());
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "대중교통 샘플 데이터 파일을 읽을 수 없습니다: " + TRANSIT_POINTS_RESOURCE,
                    exception);
        }
    }

    public enum MapDataSource {
        TIDB("tidb"),
        FALLBACK_JSON("fallback-json");

        private final String headerValue;

        MapDataSource(String headerValue) {
            this.headerValue = headerValue;
        }

        public String headerValue() {
            return headerValue;
        }
    }
}
