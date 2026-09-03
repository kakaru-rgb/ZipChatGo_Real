package com.onrender.zipchatgo.ai;

import java.util.List;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AiUiAction(
        String type,
        Double lat,
        Double lng,
        Integer zoom,
        List<Long> propertyIds,
        Long propertyId) {
}
