package com.onrender.zipchatgo.member;

import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class MemberService {

    private final MemberRepository memberRepository;
    private final PasswordEncoder passwordEncoder;

    /**
     * 회원가입 (일반회원 전용, 이번 작업 범위)
     */
    public Member signup(String email, String rawPassword, String name, String phone) {
        if (memberRepository.existsByEmail(email)) {
            throw new IllegalStateException("이미 가입된 이메일입니다.");
        }

        Member member = new Member();
        member.setEmail(email);
        member.setPassword(passwordEncoder.encode(rawPassword));
        member.setName(name);
        member.setPhone(phone);
        member.setMemberType("GENERAL");

        return memberRepository.save(member);
    }

    /**
     * 로그인 검증 - 성공 시 Member 반환, 실패 시 예외 발생
     */
    public Member login(String email, String rawPassword) {
        Member member = memberRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalStateException("존재하지 않는 이메일입니다."));

        if (!passwordEncoder.matches(rawPassword, member.getPassword())) {
            throw new IllegalStateException("이메일 또는 비밀번호가 일치하지 않습니다.");
        }

        return member;
    }
}
