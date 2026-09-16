package com.onrender.zipchatgo.ai;

import java.util.List;
import java.util.Map;

public record AiChatRequest(
        String message,
        Map<String, Object> appState,
        List<AiConversationMessage> history,
        AiRecentContext recentContext) {
}
