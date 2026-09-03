package com.onrender.zipchatgo.controller;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import com.onrender.zipchatgo.service.MapDataService;
import com.onrender.zipchatgo.service.MapDataService.GeoBounds;
import com.onrender.zipchatgo.service.MapDataService.MapDataResult;
import com.onrender.zipchatgo.service.MapDataService.PropertySearchResult;
import com.onrender.zipchatgo.service.MapDataService.TransitStationSearchResult;
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
        GeoBounds bounds = createBounds(south, west, north, east);

        PropertySearchResult result = mapDataService.searchProperties(
                keyword, propertyType, maxPrice, legalDongCode, limit, bounds);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("total_count", result.totalCount());
        body.put("properties", result.properties());

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

    private ResponseEntity<List<Map<String, Object>>> jsonResponse(MapDataResult result) {
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(Duration.ofMinutes(10)).cachePublic())
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-Map-Data-Source", result.source().headerValue())
                .body(result.data());
    }
}
