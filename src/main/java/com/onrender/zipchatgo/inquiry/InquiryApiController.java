package com.onrender.zipchatgo.inquiry;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class InquiryApiController {

	private final InquiryService inquiryService;

	public InquiryApiController(InquiryService inquiryService) {
		this.inquiryService = inquiryService;
	}

	@PostMapping("/api/inquiries")
	public ResponseEntity<Map<String, String>> create(
			@RequestParam String name,
			@RequestParam String email,
			@RequestParam String type,
			@RequestParam String title,
			@RequestParam String message,
			@RequestParam(name = "privacyAgreed", defaultValue = "false") boolean privacyAgreed) {
		inquiryService.create(name, email, type, title, message, privacyAgreed);
		return ResponseEntity.status(HttpStatus.CREATED)
				.body(Map.of("message", "문의가 정상적으로 접수되었습니다."));
	}

	@ExceptionHandler(IllegalArgumentException.class)
	public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException exception) {
		return ResponseEntity.badRequest().body(Map.of("message", exception.getMessage()));
	}
}
