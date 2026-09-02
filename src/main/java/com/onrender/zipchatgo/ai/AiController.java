package com.onrender.zipchatgo.ai;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/ai")
public class AiController {
	private final AiService aiService;

	public AiController(AiService aiService) {
		this.aiService = aiService;
	}

	@PostMapping("/test")
	public AiTestResponse testConnection() {
		return aiService.testConnection();
	}

	@PostMapping("/chat")
	public AiChatResponse chat(@RequestBody AiChatRequest request) {
		return aiService.chat(request);
	}
}
