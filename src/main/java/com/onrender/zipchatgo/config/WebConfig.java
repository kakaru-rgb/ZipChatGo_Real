package com.onrender.zipchatgo.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
@RequiredArgsConstructor
public class WebConfig implements WebMvcConfigurer {

	// MemberRepository가 필요해서 Spring Bean으로 등록된 AdminInterceptor를 주입받음.
	private final AdminInterceptor adminInterceptor;

	@Override
	public void addResourceHandlers(ResourceHandlerRegistry registry) {
		// classpath:/static/ 은 Spring Boot가 기본적으로 "/" 에도 자동 서빙하므로
		// 이 등록은 /static/** 형태의 링크(guide.html 등)와의 호환을 위해 유지.
		registry.addResourceHandler("/static/**").addResourceLocations("classpath:/static/");

		// /templates/** 는 제거함:
		// Thymeleaf 렌더링과 SecurityConfig의 인증/인가 규칙을 우회하는 문제가 있었음.
	}

	@Override
	public void addInterceptors(InterceptorRegistry registry) {
		// 로그인이 필요한 페이지만 명시적으로 지정 (화이트리스트 아닌 명시적 보호 목록 방식).
		registry.addInterceptor(new AuthInterceptor())
			.addPathPatterns(
				"/favorite",
				"/properties/map",
				"/property/register",
				"/market/trend"
			);

		// 관리자 전용 경로 (API + 나중에 만들 관리자 페이지 둘 다 미리 포함)
		registry.addInterceptor(adminInterceptor)
			.addPathPatterns(
				"/api/admin/**",
				"/admin/**"
			);
	}
}
