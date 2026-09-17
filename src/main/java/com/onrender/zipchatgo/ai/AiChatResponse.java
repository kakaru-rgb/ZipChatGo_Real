package com.onrender.zipchatgo.ai;

import java.util.List;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AiChatResponse(
        String message,
        List<AiUiAction> actions,
        AiRecentContext recentContext) {
}
