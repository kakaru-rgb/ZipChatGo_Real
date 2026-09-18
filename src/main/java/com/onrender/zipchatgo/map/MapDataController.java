package com.onrender.zipchatgo.map;

import java.time.Duration;

import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/map")
public class MapDataController {

    private final MapDataService mapDataService;

    public MapDataController(MapDataService mapDataService) {
        this.mapDataService = mapDataService;
    }

    @GetMapping(value = "/properties", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> properties() {
        return jsonResponse(mapDataService.getProperties());
    }

    @GetMapping(value = "/pois", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> pois() {
        return jsonResponse(mapDataService.getPois());
    }

    private ResponseEntity<byte[]> jsonResponse(byte[] data) {
        return ResponseEntity.ok()
                .cacheControl(CacheControl.maxAge(Duration.ofMinutes(10)).cachePublic())
                .contentType(MediaType.APPLICATION_JSON)
                .body(data);
    }
}
