package com.onrender.zipchatgo.property;

import com.onrender.zipchatgo.member.Member;
import com.onrender.zipchatgo.member.MemberRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * 매물 승인/거절 API. 실제 접근 제어는 AdminInterceptor(/api/admin/**)가 담당하므로
 * 여기서는 별도 권한 체크 없이 로직만 처리한다.
 */
@RestController
@RequestMapping("/api/admin/properties")
@RequiredArgsConstructor
public class AdminPropertyController {

    private final MemberPropertyRepository memberPropertyRepository;
    private final MemberRepository memberRepository;

    // status 파라미터 없으면 기본 PENDING. 관리자 페이지의 탭(대기중/승인됨/거절됨)이 이걸 그대로 호출.
    @GetMapping
    public List<Map<String, Object>> list(@RequestParam(required = false) String status) {
        String targetStatus = (status == null || status.isBlank()) ? "PENDING" : status;
        List<MemberProperty> properties = memberPropertyRepository.findByStatus(targetStatus);

        List<Map<String, Object>> result = new ArrayList<>();
        for (MemberProperty p : properties) {
            Map<String, Object> view = new HashMap<>();
            view.put("property", p);

            Optional<Member> registrant = memberRepository.findById(p.getMemberId());
            view.put("registrantName", registrant.map(Member::getName).orElse("알 수 없음"));
            view.put("registrantEmail", registrant.map(Member::getEmail).orElse(""));

            result.add(view);
        }
        return result;
    }

    // 기존에 테스트했던 경로도 그대로 유지 (내부적으로 list()와 동일)
    @GetMapping("/pending")
    public List<Map<String, Object>> pending() {
        return list("PENDING");
    }

    @PostMapping("/{id}/approve")
    public Map<String, Object> approve(@PathVariable Long id) {
        return updateStatus(id, "APPROVED");
    }

    @PostMapping("/{id}/reject")
    public Map<String, Object> reject(@PathVariable Long id) {
        return updateStatus(id, "REJECTED");
    }

    private Map<String, Object> updateStatus(Long id, String status) {
        Map<String, Object> result = new HashMap<>();

        Optional<MemberProperty> opt = memberPropertyRepository.findById(id);
        if (opt.isEmpty()) {
            result.put("success", false);
            result.put("message", "매물을 찾을 수 없습니다.");
            return result;
        }

        MemberProperty property = opt.get();
        property.setStatus(status);
        memberPropertyRepository.save(property);

        result.put("success", true);
        result.put("propertyId", id);
        result.put("status", status);
        return result;
    }
}

