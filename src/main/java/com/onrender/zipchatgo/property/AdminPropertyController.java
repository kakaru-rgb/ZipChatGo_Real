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
    private final PropertyDocumentRepository propertyDocumentRepository;
    private final PropertyPhotoRepository propertyPhotoRepository;
    private final SupabaseStorageService supabaseStorageService;

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

    // 특정 매물에 첨부된 서류 목록 + 열람용 서명URL (10분간 유효)
    @GetMapping("/{id}/documents")
    public List<Map<String, Object>> documents(@PathVariable Long id) {
        List<PropertyDocument> docs = propertyDocumentRepository.findByPropertyId(id);

        List<Map<String, Object>> result = new ArrayList<>();
        for (PropertyDocument d : docs) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", d.getId());
            item.put("docType", d.getDocType());
            item.put("originalName", d.getOriginalName());
            item.put("signedUrl", supabaseStorageService.createSignedUrl(d.getFilePath(), 600));
            result.add(item);
        }
        return result;
    }

    // 특정 매물의 사진 목록 + 열람용 서명URL
    @GetMapping("/{id}/photos")
    public List<Map<String, Object>> photos(@PathVariable Long id) {
        List<PropertyPhoto> photoList = propertyPhotoRepository.findByPropertyIdOrderByIdAsc(id);

        List<Map<String, Object>> result = new ArrayList<>();
        for (PropertyPhoto p : photoList) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", p.getId());
            item.put("originalName", p.getOriginalName());
            item.put("signedUrl", supabaseStorageService.createSignedUrl(p.getFilePath(), 600));
            result.add(item);
        }
        return result;
    }

    @PostMapping("/{id}/approve")
    public Map<String, Object> approve(@PathVariable Long id) {
        return updateStatus(id, "APPROVED");
    }

    @PostMapping("/{id}/reject")
    public Map<String, Object> reject(@PathVariable Long id) {
        return updateStatus(id, "REJECTED");
    }

    /**
     * 매물을 완전히 삭제한다. Supabase에 올라간 서류/사진 파일까지 같이 지우고,
     * DB에서도 서류/사진/매물(및 태그·옵션 등 속성) 전부 삭제한다.
     */
    @DeleteMapping("/{id}")
    public Map<String, Object> delete(@PathVariable Long id) {
        Map<String, Object> result = new HashMap<>();

        Optional<MemberProperty> opt = memberPropertyRepository.findById(id);
        if (opt.isEmpty()) {
            result.put("success", false);
            result.put("message", "매물을 찾을 수 없습니다.");
            return result;
        }

        List<PropertyDocument> docs = propertyDocumentRepository.findByPropertyId(id);
        List<PropertyPhoto> photoList = propertyPhotoRepository.findByPropertyIdOrderByIdAsc(id);

        List<String> filePaths = new ArrayList<>();
        docs.forEach(d -> filePaths.add(d.getFilePath()));
        photoList.forEach(p -> filePaths.add(p.getFilePath()));

        // Supabase에 올라간 실제 파일 삭제 (실패해도 아래 DB 정리는 계속 진행됨)
        supabaseStorageService.deleteObjects(filePaths);

        propertyDocumentRepository.deleteAll(docs);
        propertyPhotoRepository.deleteAll(photoList);
        // MemberProperty 삭제 시 @MappedCollection으로 연결된 property_attribute(태그/옵션 등)도 함께 삭제됨
        memberPropertyRepository.deleteById(id);

        result.put("success", true);
        result.put("propertyId", id);
        return result;
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


