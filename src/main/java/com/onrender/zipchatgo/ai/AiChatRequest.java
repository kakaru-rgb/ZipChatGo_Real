package com.onrender.zipchatgo.ai;

import java.util.Map;

public record AiChatRequest(String message, Map<String, Object> appState) {
}
