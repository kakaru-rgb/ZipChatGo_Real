package com.onrender.zipchatgo.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

	@Bean
	SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
		http
			// /api/** 는 JSON + fetch 방식이라 CSRF 토큰을 별도로 안 보내므로 예외 처리
			.csrf(csrf -> csrf.ignoringRequestMatchers("/api/**"))
			.authorizeHttpRequests(authorize -> authorize
				.anyRequest().permitAll())
			.formLogin(form -> form.disable())
			.logout(logout -> logout.disable());
		return http.build();
	}

	// 회원가입/로그인 비밀번호 암호화용
	@Bean
	PasswordEncoder passwordEncoder() {
		return new BCryptPasswordEncoder();
	}
}
