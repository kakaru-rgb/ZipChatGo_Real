package com.onrender.zipchatgo.inquiry;

import java.time.LocalDateTime;
import java.util.Set;
import java.util.regex.Pattern;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class InquiryService {

	private static final Set<String> ALLOWED_TYPES = Set.of("서비스 이용", "계정 및 로그인", "매물 정보", "오류 신고", "기타");
	private static final Pattern EMAIL_PATTERN = Pattern.compile("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
	private final InquiryRepository inquiryRepository;

	public InquiryService(InquiryRepository inquiryRepository) {
		this.inquiryRepository = inquiryRepository;
	}

	@Transactional
	public Inquiry create(String name, String email, String type, String title, String message, boolean privacyAgreed) {
		validate(name, email, type, title, message, privacyAgreed);
		return inquiryRepository.save(new Inquiry(null, null, name.trim(), email.trim(), type,
				title.trim(), message.trim(), "RECEIVED", LocalDateTime.now()));
	}

	private void validate(String name, String email, String type, String title, String message, boolean privacyAgreed) {
		if (!privacyAgreed) throw new IllegalArgumentException("개인정보 수집 및 이용 동의가 필요합니다.");
		if (isBlank(name) || name.trim().length() > 50) throw new IllegalArgumentException("이름을 확인해 주세요.");
		if (isBlank(email) || email.trim().length() > 255 || !EMAIL_PATTERN.matcher(email.trim()).matches()) {
			throw new IllegalArgumentException("이메일을 확인해 주세요.");
		}
		if (!ALLOWED_TYPES.contains(type)) throw new IllegalArgumentException("문의 유형을 선택해 주세요.");
		if (isBlank(title) || title.trim().length() > 80) throw new IllegalArgumentException("문의 제목을 확인해 주세요.");
		if (isBlank(message) || message.trim().length() > 1000) throw new IllegalArgumentException("문의 내용을 확인해 주세요.");
	}

	private boolean isBlank(String value) {
		return value == null || value.isBlank();
	}
}
