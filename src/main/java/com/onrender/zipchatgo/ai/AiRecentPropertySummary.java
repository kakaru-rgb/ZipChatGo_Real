package com.onrender.zipchatgo.ai;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AiRecentPropertySummary(
        Long id,
        String title,
        Long salePrice,
        Double latitude,
        Double longitude) {
}
