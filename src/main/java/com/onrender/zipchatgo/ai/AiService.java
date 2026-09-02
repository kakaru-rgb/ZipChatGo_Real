package com.onrender.zipchatgo.ai;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

@Service
public class AiService {
	private final RestClient aiRestClient;

	public AiService(RestClient aiRestClient) {
		this.aiRestClient = aiRestClient;
	}

	public AiTestResponse testConnection() {
		try {
			return aiRestClient.post()
					.uri("/agent/test")
					.retrieve()
					.body(AiTestResponse.class);
		} catch (RestClientException exception) {
			throw new ResponseStatusException(
					HttpStatus.BAD_GATEWAY,
					"FastAPI server request failed",
					exception);
		}
	}

	public AiChatResponse chat(AiChatRequest request) {
		try {
			return aiRestClient.post()
					.uri("/agent/chat")
					.body(request)
					.retrieve()
					.body(AiChatResponse.class);
		} catch (RestClientException exception) {
			throw new ResponseStatusException(
					HttpStatus.BAD_GATEWAY,
					"FastAPI server request failed",
					exception);
		}
	}
}
