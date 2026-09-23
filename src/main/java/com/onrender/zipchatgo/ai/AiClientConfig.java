package com.onrender.zipchatgo.ai;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@Configuration
public class AiClientConfig {

	@Bean
	RestClient aiRestClient(
			@Value("${ai.server.base-url}") String baseUrl,
			@Value("${internal.api-key:}") String internalApiKey) {
		RestClient.Builder builder = RestClient.builder()
				.baseUrl(baseUrl)
				.requestFactory(new SimpleClientHttpRequestFactory());
		if (!internalApiKey.isBlank()) {
			builder.defaultHeader("X-Internal-API-Key", internalApiKey);
		}
		return builder.build();
	}
}
