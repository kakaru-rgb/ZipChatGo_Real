package com.onrender.zipchatgo.ai;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestClient;

class AiControllerTests {

	@Test
	void forwardsTestRequestToFastApi() throws Exception {
		RestClient.Builder restClientBuilder = RestClient.builder().baseUrl("http://localhost:8000");
		MockRestServiceServer fastApi = MockRestServiceServer.bindTo(restClientBuilder).build();
		AiService aiService = new AiService(restClientBuilder.build());
		MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new AiController(aiService)).build();

		fastApi.expect(requestTo("http://localhost:8000/agent/test"))
				.andExpect(method(HttpMethod.POST))
				.andRespond(withSuccess("{\"message\":\"hello\"}", MediaType.APPLICATION_JSON));

		mockMvc.perform(post("/api/ai/test"))
				.andExpect(status().isOk())
				.andExpect(content().json("{\"message\":\"hello\"}"));

		fastApi.verify();
	}

	@Test
	void forwardsChatRequestToFastApi() throws Exception {
		RestClient.Builder restClientBuilder = RestClient.builder().baseUrl("http://localhost:8000");
		MockRestServiceServer fastApi = MockRestServiceServer.bindTo(restClientBuilder).build();
		AiService aiService = new AiService(restClientBuilder.build());
		MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new AiController(aiService)).build();

		fastApi.expect(requestTo("http://localhost:8000/agent/chat"))
				.andExpect(method(HttpMethod.POST))
				.andExpect(org.springframework.test.web.client.match.MockRestRequestMatchers
						.content().json("""
								{
								  "message": "안녕하세요",
								  "appState": {
								    "current_page": "map",
								    "selected_property_id": "427"
								  }
								}
								"""))
				.andRespond(withSuccess("""
						{
						  "message": "조건에 맞는 매물을 찾았습니다.",
						  "actions": [
						    {
						      "type": "MOVE_MAP",
						      "lat": 37.394,
						      "lng": 127.111,
						      "zoom": 17
						    },
						    {
						      "type": "HIGHLIGHT_PROPERTIES",
						      "property_ids": [427]
						    }
						  ]
						}
						""", MediaType.APPLICATION_JSON));

		mockMvc.perform(post("/api/ai/chat")
					.contentType(MediaType.APPLICATION_JSON)
					.content("""
							{
							  "message": "안녕하세요",
							  "appState": {
							    "current_page": "map",
							    "selected_property_id": "427"
							  }
							}
							"""))
				.andExpect(status().isOk())
				.andExpect(content().json("""
						{
						  "message": "조건에 맞는 매물을 찾았습니다.",
						  "actions": [
						    {
						      "type": "MOVE_MAP",
						      "lat": 37.394,
						      "lng": 127.111,
						      "zoom": 17
						    },
						    {
						      "type": "HIGHLIGHT_PROPERTIES",
						      "property_ids": [427]
						    }
						  ]
						}
						"""));

		fastApi.verify();
	}
}
