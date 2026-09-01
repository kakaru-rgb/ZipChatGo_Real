package com.onrender.zipchatgo.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 로그인이 필요한 페이지(예: 매물등록, 지도, 시세분석, 관심매물)에
 * 비로그인 사용자가 접근하면 로그인 페이지로 돌려보낸다.
 * 세션 기준(AuthController가 로그인 성공 시 심어두는 "loginMemberId")으로 판단한다.
 */
public class AuthInterceptor implements HandlerInterceptor {

    private static final String SESSION_KEY = "loginMemberId";

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        HttpSession session = request.getSession(false);
        boolean loggedIn = session != null && session.getAttribute(SESSION_KEY) != null;

        if (loggedIn) {
            return true;
        }

        String redirectPath = request.getRequestURI();
        response.sendRedirect("/member/login?redirect=" + redirectPath);
        return false;
    }
}
