package com.onrender.zipchatgo.member;

import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private static final String SESSION_KEY = "loginMemberId";

    private final MemberService memberService;

    /**
     * 로그인
     * body: { "email": "...", "password": "..." }
     */
    @PostMapping("/login")
    public Map<String, Object> login(@RequestBody Map<String, String> body, HttpSession session) {
        Map<String, Object> result = new HashMap<>();
        try {
            Member member = memberService.login(body.get("email"), body.get("password"));
            session.setAttribute(SESSION_KEY, member.getId());

            result.put("success", true);
            result.put("name", member.getName());
            result.put("email", member.getEmail());
        } catch (IllegalStateException e) {
            result.put("success", false);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 회원가입 (일반회원 전용)
     * body: { "email": "...", "password": "...", "name": "...", "phone": "..." }
     */
    @PostMapping("/signup")
    public Map<String, Object> signup(@RequestBody Map<String, String> body, HttpSession session) {
        Map<String, Object> result = new HashMap<>();
        try {
            Member member = memberService.signup(
                    body.get("email"),
                    body.get("password"),
                    body.get("name"),
                    body.get("phone")
            );
            // 회원가입 성공 시 바로 로그인 상태로 세션 등록 (기존 auth.js 흐름 유지)
            session.setAttribute(SESSION_KEY, member.getId());

            result.put("success", true);
            result.put("name", member.getName());
            result.put("email", member.getEmail());
        } catch (IllegalStateException e) {
            result.put("success", false);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 로그아웃
     */
    @PostMapping("/logout")
    public Map<String, Object> logout(HttpSession session) {
        session.invalidate();

        Map<String, Object> result = new HashMap<>();
        result.put("success", true);
        return result;
    }

    /**
     * 현재 로그인 상태 확인 (헤더에서 로그인/로그아웃 메뉴 표시할 때 사용)
     */
    @GetMapping("/check")
    public Map<String, Object> check(HttpSession session) {
        Object memberId = session.getAttribute(SESSION_KEY);

        Map<String, Object> result = new HashMap<>();
        result.put("loggedIn", memberId != null);
        return result;
    }
}
