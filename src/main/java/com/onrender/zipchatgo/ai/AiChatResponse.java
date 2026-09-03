package com.onrender.zipchatgo.ai;

import java.util.List;

public record AiChatResponse(String message, List<AiUiAction> actions) {
}
