package com.onrender.zipchatgo.map;

import java.awt.geom.Path2D;
import java.io.IOException;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.SQLException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
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
    private static final String LEGAL_DONG_RESOURCE = "static/data/bundang_legal_dong.geojson";
    private static final List<String> PROPERTY_SEARCH_FIELDS = List.of(
            "title", "description", "building_name", "address", "district", "lot_number");
    private static final List<String> PROPERTY_SUMMARY_FIELDS = List.of(
            "id", "title", "building_name", "property_type", "sale_price", "deposit",
            "monthly_rent", "maintenance_fee", "exclusive_area", "floor", "built_year",
            "address", "district", "latitude", "longitude", "contract_date");
    private static final List<String> POI_KEYWORD_FIELDS = List.of(
            "name", "category", "subcategory", "source_type", "road_address");
    private static final List<String> POI_REGION_FIELDS = List.of(
            "road_address", "province", "city", "town");
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

    private static final String PROPERTIES_SQL_TEMPLATE = """
            SELECT id, title, description, building_name, property_type,
                   sale_price, deposit, monthly_rent, maintenance_fee,
                   exclusive_area, floor, built_year, address, district,
                   lot_number, latitude, longitude, thumbnail_url,
                   contract_date, created_at, updated_at
              FROM properties
             WHERE contract_date >= DATE_SUB(
                       DATE_FORMAT(CURRENT_DATE(), '%%Y-%%m-01'), INTERVAL %d MONTH
                   )
               AND contract_date < DATE_ADD(
                       LAST_DAY(CURRENT_DATE()), INTERVAL 1 DAY
                   )
            ORDER BY id
            """;
    private static final String PROPERTIES_SQL = PROPERTIES_SQL_TEMPLATE.formatted(12);
    private static final String TRANSACTION_PROPERTIES_SQL = PROPERTIES_SQL_TEMPLATE.formatted(36);

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
    private final Map<String, Path2D.Double> legalDongPolygons;

    public MapDataService(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
        this.fallbackProperties = readFallback(PROPERTIES_RESOURCE);
        this.fallbackPois = readFallback(POIS_RESOURCE);
        this.transitStations = readTransitStations();
        this.legalDongPolygons = readLegalDongPolygons();
    }

    public MapDataResult getProperties() {
        return queryOrFallback("properties", PROPERTIES_SQL, fallbackProperties);
    }

    public MapDataResult getPois() {
        return queryOrFallback("poi", POIS_SQL, fallbackPois);
    }

    public MapDataResult getMapPois() {
        MapDataResult result = getPois();
        return new MapDataResult(searchablePois(result.data()), result.source());
    }

    public PoiSearchResult searchPois(
            String category,
            String subcategory,
            String region,
            String keyword,
            Double latitude,
            Double longitude,
            Integer radiusMeters,
            int limit) {
        return searchPois(category, subcategory, region, keyword,
                latitude, longitude, radiusMeters, limit, null);
    }

    public PoiSearchResult searchPois(
            String category,
            String subcategory,
            String region,
            String keyword,
            Double latitude,
            Double longitude,
            Integer radiusMeters,
            int limit,
            String legalDongCode) {
        MapDataResult allPois = getPois();
        String normalizedCategory = normalize(category);
        String normalizedSubcategory = normalize(subcategory);
        String normalizedRegion = normalize(region);
        String normalizedKeyword = normalize(keyword);
        boolean distanceSearch = latitude != null && longitude != null;
        Path2D.Double legalDong = legalDongCode == null ? null : legalDongPolygons.get(legalDongCode);

        List<PoiDistance> matches = searchablePois(allPois.data()).stream()
                .filter(poi -> normalizedCategory.isEmpty()
                        || normalizedCategory.equals(normalize(poi.get("category"))))
                .filter(poi -> normalizedSubcategory.isEmpty()
                        || normalize(poi.get("subcategory")).contains(normalizedSubcategory))
                .filter(poi -> normalizedRegion.isEmpty()
                        || matchesAnyField(poi, POI_REGION_FIELDS, normalizedRegion))
                .filter(poi -> legalDongCode == null || legalDong != null
                        && legalDong.contains(coordinateOf(poi, "longitude"), coordinateOf(poi, "latitude")))
                .filter(poi -> normalizedKeyword.isEmpty()
                        || matchesAnyField(poi, POI_KEYWORD_FIELDS, normalizedKeyword))
                .map(poi -> new PoiDistance(
                        poi,
                        distanceSearch
                                ? distanceMeters(
                                        latitude,
                                        longitude,
                                        coordinateOf(poi, "latitude"),
                                        coordinateOf(poi, "longitude"))
                                : null))
                .filter(match -> !distanceSearch || match.distanceMeters() != null)
                .filter(match -> radiusMeters == null
                        || match.distanceMeters() != null
                        && match.distanceMeters() <= radiusMeters)
                .sorted(distanceSearch
                        ? Comparator.comparingDouble(PoiDistance::distanceMeters)
                        : Comparator.comparing(match -> normalize(match.poi().get("name"))))
                .toList();

        List<Map<String, Object>> pois = matches.stream()
                .limit(limit)
                .map(this::summarizePoi)
                .toList();
        return new PoiSearchResult(pois, matches.size(), allPois.source());
    }

    public PropertySearchResult searchProperties(
            String keyword,
            String propertyType,
            Long maxPrice,
            String legalDongCode,
            int limit,
            GeoBounds bounds) {
        return searchProperties(
                keyword, propertyType, maxPrice, legalDongCode, limit, bounds, null, null);
    }

    public PropertySearchResult searchProperties(
            String keyword,
            String propertyType,
            Long maxPrice,
            String legalDongCode,
            int limit,
            GeoBounds bounds,
            String sortBy,
            String sortOrder) {
        return searchProperties(keyword, propertyType, maxPrice, legalDongCode, limit, bounds,
                sortBy, sortOrder, "properties", null, null, null);
    }

    public PropertySearchResult searchProperties(
            String keyword,
            String propertyType,
            Long maxPrice,
            String legalDongCode,
            int limit,
            GeoBounds bounds,
            String sortBy,
            String sortOrder,
            String searchMode,
            Long selectedPropertyId,
            String exactBuildingName,
            Double exclusiveArea) {
        boolean transactionHistory = !"properties".equals(searchMode);
        MapDataResult allProperties = transactionHistory ? getTransactionProperties() : getProperties();
        Map<String, Object> selectedProperty = selectedPropertyId == null ? null
                : allProperties.data().stream()
                        .filter(property -> selectedPropertyId.equals(propertyIdOf(property)))
                        .findFirst().orElse(null);
        if ("selected_building_transactions".equals(searchMode) && selectedProperty == null) {
            return new PropertySearchResult(List.of(), 0, allProperties.source());
        }
        String normalizedKeyword = normalize(keyword);
        String stationKeyword = normalizedKeyword.endsWith("역") && normalizedKeyword.length() > 1
                ? normalizedKeyword.substring(0, normalizedKeyword.length() - 1)
                : normalizedKeyword;
        String normalizedType = normalize(propertyType);
        String normalizedLegalDongCode = normalize(legalDongCode);
        String legalDongName = BUNDANG_LEGAL_DONG_NAMES.get(normalizedLegalDongCode);
        String exactBuildingKey = buildingKey(exactBuildingName);

        List<Map<String, Object>> matches = allProperties.data().stream()
                .filter(property -> matchesKeyword(property, normalizedKeyword, stationKeyword))
                .filter(property -> exactBuildingKey.isEmpty()
                        || exactBuildingKey.equals(buildingKey(property.get("building_name"))))
                .filter(property -> selectedProperty == null || sameBuilding(property, selectedProperty))
                .filter(property -> normalizedLegalDongCode.isEmpty()
                        || legalDongName != null && matchesLegalDong(property, legalDongName))
                .filter(property -> normalizedType.isEmpty()
                        || normalizedType.equals(normalize(property.get("property_type"))))
                .filter(property -> maxPrice == null || priceOf(property) <= maxPrice)
                .filter(property -> exclusiveArea == null || matchesExclusiveArea(property, exclusiveArea))
                .filter(property -> !transactionHistory || !LocalDate.MIN.equals(contractDateOf(property)))
                .filter(property -> bounds == null || bounds.contains(
                        coordinateOf(property, "latitude"),
                        coordinateOf(property, "longitude")))
                .toList();

        if (transactionHistory && selectedProperty == null && !exactBuildingKey.isEmpty()
                && normalizedLegalDongCode.isEmpty()
                && matches.stream().map(this::buildingLocationKey).distinct().limit(2).count() > 1) {
            return new PropertySearchResult(List.of(), 0, allProperties.source(), true);
        }

        if ("sale_price".equals(sortBy)) {
            Comparator<Map<String, Object>> comparator = Comparator.comparingLong(this::priceOf);
            if ("desc".equals(sortOrder)) {
                comparator = comparator.reversed();
            }
            matches = matches.stream().sorted(comparator).toList();
        } else if ("contract_date".equals(sortBy) || transactionHistory) {
            Comparator<Map<String, Object>> comparator = Comparator.comparing(this::contractDateOf)
                    .thenComparing(property -> propertyIdOf(property),
                            Comparator.nullsFirst(Comparator.naturalOrder()));
            matches = matches.stream().sorted("asc".equals(sortOrder) && !transactionHistory
                    ? comparator : comparator.reversed()).toList();
        }

        List<Map<String, Object>> summaries = matches.stream()
                .limit(limit)
                .map(this::summarizeProperty)
                .toList();

        return new PropertySearchResult(summaries, matches.size(), allProperties.source());
    }

    private MapDataResult getTransactionProperties() {
        return new MapDataResult(
                jdbcTemplate.query(TRANSACTION_PROPERTIES_SQL, this::mapRow), MapDataSource.TIDB);
    }

    private String buildingKey(Object value) {
        return normalize(value).replaceAll("[\\s()（）\\[\\]]", "");
    }

    private String buildingLocationKey(Map<String, Object> property) {
        String district = normalize(property.get("district"));
        return district.isEmpty() ? normalize(property.get("address")) : district;
    }

    private boolean sameBuilding(Map<String, Object> candidate, Map<String, Object> selected) {
        String name = buildingKey(selected.get("building_name"));
        String location = buildingLocationKey(selected);
        return !name.isEmpty() && !location.isEmpty()
                && name.equals(buildingKey(candidate.get("building_name")))
                && location.equals(buildingLocationKey(candidate));
    }

    private boolean matchesExclusiveArea(Map<String, Object> property, double requestedArea) {
        double area = coordinateOf(property, "exclusive_area");
        return Double.isFinite(area) && (requestedArea == Math.floor(requestedArea)
                ? Math.floor(area) == requestedArea
                : Math.abs(area - requestedArea) < 0.01);
    }

    private LocalDate contractDateOf(Map<String, Object> property) {
        Object value = property.get("contract_date");
        if (value == null) return LocalDate.MIN;
        String date = value.toString();
        try {
            return LocalDate.parse(date.length() >= 10 ? date.substring(0, 10) : date);
        } catch (java.time.format.DateTimeParseException exception) {
            return LocalDate.MIN;
        }
    }

    public PropertiesByIdsResult getPropertiesByIds(List<Long> propertyIds) {
        MapDataResult allProperties = getProperties();
        LinkedHashSet<Long> requestedIds = new LinkedHashSet<>(propertyIds);
        Map<Long, Map<String, Object>> propertiesById = new LinkedHashMap<>();
        for (Map<String, Object> property : allProperties.data()) {
            Long id = propertyIdOf(property);
            if (id != null && requestedIds.contains(id)) {
                propertiesById.put(id, summarizeProperty(property));
            }
        }

        List<Map<String, Object>> properties = requestedIds.stream()
                .map(propertiesById::get)
                .filter(java.util.Objects::nonNull)
                .toList();
        List<Long> missingIds = requestedIds.stream()
                .filter(id -> !propertiesById.containsKey(id))
                .toList();
        return new PropertiesByIdsResult(
                List.copyOf(requestedIds), properties, missingIds, allProperties.source());
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

    private boolean matchesAnyField(
            Map<String, Object> item,
            List<String> fields,
            String expected) {
        return fields.stream()
                .map(item::get)
                .map(this::normalize)
                .anyMatch(value -> value.contains(expected));
    }

    private Double distanceMeters(
            double originLatitude,
            double originLongitude,
            double targetLatitude,
            double targetLongitude) {
        if (!Double.isFinite(targetLatitude) || !Double.isFinite(targetLongitude)) {
            return null;
        }
        double earthRadiusMeters = 6_371_000.0;
        double latitudeDelta = Math.toRadians(targetLatitude - originLatitude);
        double longitudeDelta = Math.toRadians(targetLongitude - originLongitude);
        double originLatitudeRadians = Math.toRadians(originLatitude);
        double targetLatitudeRadians = Math.toRadians(targetLatitude);
        double haversine = Math.sin(latitudeDelta / 2) * Math.sin(latitudeDelta / 2)
                + Math.cos(originLatitudeRadians) * Math.cos(targetLatitudeRadians)
                * Math.sin(longitudeDelta / 2) * Math.sin(longitudeDelta / 2);
        return earthRadiusMeters * 2 * Math.atan2(
                Math.sqrt(haversine), Math.sqrt(1 - haversine));
    }

    private Long propertyIdOf(Map<String, Object> property) {
        Object value = property.get("id");
        if (value instanceof Number number) {
            return number.longValue();
        }
        try {
            return value == null ? null : Long.valueOf(value.toString());
        } catch (NumberFormatException ignored) {
            return null;
        }
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

    private Map<String, Object> summarizePoi(PoiDistance match) {
        Map<String, Object> poi = match.poi();
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("id", poi.get("poi_id"));
        summary.put("name", poi.get("name"));
        summary.put("category", poi.get("category"));
        summary.put("subcategory", poi.get("subcategory"));
        summary.put("address", poi.get("road_address"));
        summary.put("latitude", poi.get("latitude"));
        summary.put("longitude", poi.get("longitude"));
        if (poi.get("bus_routes") != null) {
            summary.put("bus_routes", poi.get("bus_routes"));
        }
        if (poi.get("lines") != null) {
            summary.put("lines", poi.get("lines"));
        }
        if (match.distanceMeters() != null) {
            summary.put("distance_m", Math.round(match.distanceMeters()));
        }
        return summary;
    }

    private List<Map<String, Object>> searchablePois(List<Map<String, Object>> pois) {
        List<Map<String, Object>> combined = new ArrayList<>(pois);
        Map<String, List<Map<String, Object>>> groupedStations = new LinkedHashMap<>();
        for (Map<String, Object> station : transitStations) {
            String normalizedName = normalizeStationName(station.get("name"));
            groupedStations.computeIfAbsent(normalizedName, ignored -> new ArrayList<>()).add(station);
        }
        groupedStations.forEach((normalizedName, entries) -> {
            Map<String, Object> station = summarizeStation(normalizedName, entries);
            Map<String, Object> poi = new LinkedHashMap<>();
            poi.put("poi_id", "SUBWAY_" + normalizedName);
            poi.put("source_type", "subway");
            poi.put("name", station.get("name"));
            poi.put("category", "교통");
            poi.put("subcategory", "지하철역");
            poi.put("latitude", station.get("latitude"));
            poi.put("longitude", station.get("longitude"));
            poi.put("lines", station.get("lines"));
            combined.add(poi);
        });
        return combined;
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
            MapDataSource source,
            boolean ambiguous) {
        public PropertySearchResult(List<Map<String, Object>> properties, int totalCount, MapDataSource source) {
            this(properties, totalCount, source, false);
        }
    }

    public record PropertiesByIdsResult(
            List<Long> requestedIds,
            List<Map<String, Object>> properties,
            List<Long> missingIds,
            MapDataSource source) {}

    public record PoiSearchResult(
            List<Map<String, Object>> pois,
            int totalCount,
            MapDataSource source) {}

    private record PoiDistance(Map<String, Object> poi, Double distanceMeters) {}

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

    private Map<String, Path2D.Double> readLegalDongPolygons() {
        try {
            Map<String, Object> geoJson = objectMapper.readValue(
                    new ClassPathResource(LEGAL_DONG_RESOURCE).getInputStream(),
                    new TypeReference<Map<String, Object>>() {});
            Map<String, Path2D.Double> polygons = new LinkedHashMap<>();
            if (geoJson.get("features") instanceof List<?> features) {
                for (Object featureValue : features) {
                    if (!(featureValue instanceof Map<?, ?> feature)
                            || !(feature.get("properties") instanceof Map<?, ?> properties)
                            || !(feature.get("geometry") instanceof Map<?, ?> geometry)) {
                        continue;
                    }
                    Object code = properties.get("legal_dong_code");
                    Object coordinates = geometry.get("coordinates");
                    if (!(code instanceof String) || !(coordinates instanceof List<?> parts)) {
                        continue;
                    }
                    Path2D.Double path = new Path2D.Double(Path2D.WIND_EVEN_ODD);
                    if ("Polygon".equals(geometry.get("type"))) {
                        appendPolygon(path, parts);
                    } else if ("MultiPolygon".equals(geometry.get("type"))) {
                        for (Object part : parts) {
                            appendPolygon(path, part);
                        }
                    }
                    polygons.put((String) code, path);
                }
            }
            return Map.copyOf(polygons);
        } catch (IOException exception) {
            throw new IllegalStateException("법정동 경계 데이터를 읽을 수 없습니다: " + LEGAL_DONG_RESOURCE, exception);
        }
    }

    private void appendPolygon(Path2D.Double path, Object polygonValue) {
        if (!(polygonValue instanceof List<?> rings)) return;
        for (Object ringValue : rings) {
            if (!(ringValue instanceof List<?> ring)) continue;
            boolean first = true;
            for (Object pointValue : ring) {
                if (!(pointValue instanceof List<?> point) || point.size() < 2
                        || !(point.get(0) instanceof Number lng)
                        || !(point.get(1) instanceof Number lat)) continue;
                if (first) {
                    path.moveTo(lng.doubleValue(), lat.doubleValue());
                    first = false;
                } else {
                    path.lineTo(lng.doubleValue(), lat.doubleValue());
                }
            }
            if (!first) path.closePath();
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
