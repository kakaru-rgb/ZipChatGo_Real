package com.onrender.zipchatgo.map;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.onrender.zipchatgo.map.MapDataService.GeoBounds;
import com.onrender.zipchatgo.map.MapDataService.MapDataResult;
import com.onrender.zipchatgo.map.MapDataService.PropertySearchResult;
import com.onrender.zipchatgo.map.MapDataService.PropertiesByIdsResult;
import com.onrender.zipchatgo.map.MapDataService.PoiSearchResult;
import com.onrender.zipchatgo.map.MapDataService.TransitStationSearchResult;

import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@RestController
@RequestMapping("/api/map")
public class MapDataController {

    private final MapDataService mapDataService;

    public MapDataController(MapDataService mapDataService) {
        this.mapDataService = mapDataService;
    }

    @GetMapping(value = "/properties", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<Map<String, Object>>> properties() {
        return jsonResponse(mapDataService.getProperties());
    }

    @GetMapping(value = "/properties/search", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> searchProperties(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) String propertyType,
            @RequestParam(required = false) Long maxPrice,
            @RequestParam(required = false) String legalDongCode,
            @RequestParam(required = false) Double south,
            @RequestParam(required = false) Double west,
            @RequestParam(required = false) Double north,
            @RequestParam(required = false) Double east,
            @RequestParam(required = false) String sortBy,
            @RequestParam(required = false) String sortOrder,
            @RequestParam(defaultValue = "10") int limit) {
        if (maxPrice != null && maxPrice < 0) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "maxPrice must be zero or greater");
        }
        if (limit < 1 || limit > 20) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit must be between 1 and 20");
        }
        if (legalDongCode != null && !legalDongCode.matches("\\d{8}")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "legalDongCode must be 8 digits");
        }
        if (sortBy != null && !"sale_price".equals(sortBy)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sortBy must be sale_price");
        }
        if (sortOrder != null && !sortOrder.matches("asc|desc")) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "sortOrder must be asc or desc");
        }
        GeoBounds bounds = createBounds(south, west, north, east);

        PropertySearchResult result = mapDataService.searchProperties(
                keyword, propertyType, maxPrice, legalDongCode, limit, bounds, sortBy, sortOrder);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("total_count", result.totalCount());
        body.put("properties", result.properties());

        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Map-Data-Source", result.source().headerValue())
                .body(body);
    }

    @GetMapping(value = "/properties/by-ids", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> propertiesByIds(@RequestParam List<Long> ids) {
        if (ids.isEmpty() || ids.size() > 50 || ids.stream().anyMatch(id -> id == null || id < 1)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "ids must contain between 1 and 50 positive values");
        }

        PropertiesByIdsResult result = mapDataService.getPropertiesByIds(ids);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("requested_ids", result.requestedIds());
        body.put("properties", result.properties());
        body.put("missing_ids", result.missingIds());

        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Map-Data-Source", result.source().headerValue())
                .body(body);
    }

    private GeoBounds createBounds(Double south, Double west, Double north, Double east) {
        boolean anyProvided = south != null || west != null || north != null || east != null;
        boolean allProvided = south != null && west != null && north != null && east != null;

        if (!anyProvided) {
            return null;
        }
        if (!allProvided
                || south < -90 || north > 90
                || west < -180 || east > 180
                || south >= north || west >= east) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "invalid map bounds");
        }
        return new GeoBounds(south, west, north, east);
    }

    @GetMapping(value = "/transit/stations/search", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> searchTransitStations(
            @RequestParam String query,
            @RequestParam(defaultValue = "5") int limit) {
        if (query.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "query must not be blank");
        }
        if (limit < 1 || limit > 10) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit must be between 1 and 10");
        }

        TransitStationSearchResult result = mapDataService.searchTransitStations(query, limit);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("total_count", result.totalCount());
        body.put("stations", result.stations());

        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(Duration.ofHours(1)).cachePublic())
                .contentType(MediaType.APPLICATION_JSON)
                .body(body);
    }

    @GetMapping(value = "/properties/{propertyId}/price-history", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<Map<String, Object>>> priceHistory(
            @PathVariable long propertyId,
            @RequestParam(defaultValue = "3") int years) {
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(Duration.ofMinutes(30)).cachePublic())
                .contentType(MediaType.APPLICATION_JSON)
                .body(mapDataService.getPriceHistory(propertyId, years));
    }

    @GetMapping(value = "/pois", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<List<Map<String, Object>>> pois() {
        return jsonResponse(mapDataService.getPois());
    }

    @GetMapping(value = "/pois/search", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<Map<String, Object>> searchPois(
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String subcategory,
            @RequestParam(required = false) String region,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Double lat,
            @RequestParam(required = false) Double lng,
            @RequestParam(required = false) Integer radius,
            @RequestParam(defaultValue = "5") int limit) {
        boolean oneCoordinateMissing = (lat == null) != (lng == null);
        if (oneCoordinateMissing
                || lat != null && (lat < -90 || lat > 90)
                || lng != null && (lng < -180 || lng > 180)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "lat and lng must be valid coordinates");
        }
        if (radius != null && (lat == null || radius < 1 || radius > 50_000)) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST, "radius requires coordinates and must be between 1 and 50000");
        }
        if (limit < 1 || limit > 20) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "limit must be between 1 and 20");
        }

        PoiSearchResult result = mapDataService.searchPois(
                category, subcategory, region, keyword, lat, lng, radius, limit);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("total_count", result.totalCount());
        body.put("pois", result.pois());

        return ResponseEntity.ok()
                .cacheControl(CacheControl.noStore())
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Map-Data-Source", result.source().headerValue())
                .body(body);
    }

    private ResponseEntity<List<Map<String, Object>>> jsonResponse(MapDataResult result) {
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(Duration.ofMinutes(10)).cachePublic())
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Map-Data-Source", result.source().headerValue())
                .body(result.data());
    }
}
