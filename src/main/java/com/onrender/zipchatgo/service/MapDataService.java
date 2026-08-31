package com.onrender.zipchatgo.service;

import java.io.IOException;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
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

    public MapDataService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.fallbackProperties = readFallback(PROPERTIES_RESOURCE);
        this.fallbackPois = readFallback(POIS_RESOURCE);
    }

    public MapDataResult getProperties() {
        return queryOrFallback("properties", PROPERTIES_SQL, fallbackProperties);
    }

    public MapDataResult getPois() {
        return queryOrFallback("poi", POIS_SQL, fallbackPois);
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
