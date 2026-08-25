package com.onrender.zipchatgo.service;

import java.io.IOException;
import java.util.Map;

import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

@Service
public class MapDataService {

    private static final String PROPERTIES_RESOURCE = "static/data/properties.json";
    private static final String POIS_RESOURCE = "static/data/poi_database.json";

    private final Map<String, byte[]> dataByName;

    public MapDataService() {
        this.dataByName = Map.of(
                "properties", readResource(PROPERTIES_RESOURCE),
                "pois", readResource(POIS_RESOURCE));
    }

    public byte[] getProperties() {
        return dataByName.get("properties");
    }

    public byte[] getPois() {
        return dataByName.get("pois");
    }

    private byte[] readResource(String path) {
        try {
            return new ClassPathResource(path).getContentAsByteArray();
        } catch (IOException exception) {
            throw new IllegalStateException("지도 데이터 파일을 읽을 수 없습니다: " + path, exception);
        }
    }
}
