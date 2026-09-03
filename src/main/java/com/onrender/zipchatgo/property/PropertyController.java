package com.onrender.zipchatgo.property;

import com.onrender.zipchatgo.member.Member;
import com.onrender.zipchatgo.member.MemberRepository;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/properties")
@RequiredArgsConstructor
public class PropertyController {

    private static final String SESSION_KEY = "loginMemberId";

    private final MemberPropertyService memberPropertyService;
    private final MemberRepository memberRepository;

    /**
     * 매물 등록. 로그인 세션이 없으면 실패 처리.
     * 등록된 매물은 항상 status=PENDING으로 시작하고, 관리자 승인 후에만 공개된다.
     */
    @PostMapping
    public Map<String, Object> register(@RequestBody PropertyRegisterRequest request, HttpSession session) {
        Map<String, Object> result = new HashMap<>();

        Object memberIdObj = session.getAttribute(SESSION_KEY);
        if (memberIdObj == null) {
            result.put("success", false);
            result.put("message", "로그인이 필요합니다.");
            return result;
        }
        Long memberId = (Long) memberIdObj;

        try {
            MemberProperty saved = memberPropertyService.register(memberId, request);

            // 집주인 이름이 회원가입 실명과 다르면 경고만 (등록 자체는 막지 않음)
            boolean nameMismatch = false;
            Optional<Member> memberOpt = memberRepository.findById(memberId);
            if (memberOpt.isPresent() && request.getOwnerName() != null) {
                String memberName = memberOpt.get().getName() == null ? "" : memberOpt.get().getName().trim();
                String ownerName = request.getOwnerName().trim();
                nameMismatch = !memberName.isEmpty() && !memberName.equals(ownerName);
            }

            result.put("success", true);
            result.put("propertyId", saved.getId());
            result.put("status", saved.getStatus());
            result.put("nameMismatch", nameMismatch);
            if (nameMismatch) {
                result.put("nameMismatchMessage",
                        "입력하신 집주인 이름이 회원가입 시 등록한 이름과 달라요. 실제 소유자가 맞는지 다시 확인해주세요.");
            }
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "매물 등록 중 오류가 발생했어요.");
        }

        return result;
    }
}
