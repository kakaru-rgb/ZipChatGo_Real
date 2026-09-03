package com.onrender.zipchatgo.config;

import com.onrender.zipchatgo.member.Member;
import com.onrender.zipchatgo.member.MemberRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.Optional;

/**
 * /api/admin/**, /admin/** 경로를 관리자(memberType=ADMIN)만 접근하도록 보호한다.
 * MemberRepository가 필요해서 (일반 페이지 가드인 AuthInterceptor와 달리) Spring Bean으로 등록해서 주입받는다.
 */
@Component
@RequiredArgsConstructor
public class AdminInterceptor implements HandlerInterceptor {

    private static final String SESSION_KEY = "loginMemberId";

    private final MemberRepository memberRepository;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        HttpSession session = request.getSession(false);
        Object memberIdObj = session != null ? session.getAttribute(SESSION_KEY) : null;

        if (memberIdObj == null) {
            writeJsonError(response, HttpServletResponse.SC_UNAUTHORIZED, "로그인이 필요합니다.");
            return false;
        }

        Long memberId = (Long) memberIdObj;
        Optional<Member> memberOpt = memberRepository.findById(memberId);
        boolean isAdmin = memberOpt.isPresent() && "ADMIN".equals(memberOpt.get().getMemberType());

        if (!isAdmin) {
            writeJsonError(response, HttpServletResponse.SC_FORBIDDEN, "관리자만 접근할 수 있습니다.");
            return false;
        }

        return true;
    }

    private void writeJsonError(HttpServletResponse response, int status, String message) throws Exception {
        response.setStatus(status);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"success\":false,\"message\":\"" + message + "\"}");
    }
}
