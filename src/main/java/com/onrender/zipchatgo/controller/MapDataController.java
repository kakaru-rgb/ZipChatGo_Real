package com.onrender.zipchatgo.controller;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import com.onrender.zipchatgo.service.MapDataService;
import com.onrender.zipchatgo.service.MapDataService.MapDataResult;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

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
