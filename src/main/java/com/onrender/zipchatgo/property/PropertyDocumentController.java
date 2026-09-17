package com.onrender.zipchatgo.property;

import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/properties/{propertyId}/documents")
@RequiredArgsConstructor
public class PropertyDocumentController {

    private static final String SESSION_KEY = "loginMemberId";

    private final PropertyDocumentRepository propertyDocumentRepository;
    private final MemberPropertyRepository memberPropertyRepository;
    private final SupabaseStorageService supabaseStorageService;

    @PostMapping
    public Map<String, Object> upload(@PathVariable Long propertyId,
                                       @RequestParam("docType") String docType,
                                       @RequestParam("file") MultipartFile file,
                                       HttpSession session) {
        Map<String, Object> result = new HashMap<>();

        Object memberIdObj = session.getAttribute(SESSION_KEY);
        if (memberIdObj == null) {
            result.put("success", false);
            result.put("message", "로그인이 필요합니다.");
            return result;
        }

        Optional<MemberProperty> propertyOpt = memberPropertyRepository.findById(propertyId);
        if (propertyOpt.isEmpty()) {
            result.put("success", false);
            result.put("message", "매물을 찾을 수 없습니다.");
            return result;
        }

        Long memberId = (Long) memberIdObj;
        if (!memberId.equals(propertyOpt.get().getMemberId())) {
            result.put("success", false);
            result.put("message", "본인이 등록한 매물에만 서류를 첨부할 수 있어요.");
            return result;
        }

        try {
            String safeName = file.getOriginalFilename() != null
                    ? file.getOriginalFilename().replaceAll("[^a-zA-Z0-9._-]", "_")
                    : "file";
            String path = propertyId + "/" + docType + "/" + System.currentTimeMillis() + "_" + safeName;

            supabaseStorageService.upload(path, file.getBytes(), file.getContentType());

            PropertyDocument doc = new PropertyDocument();
            doc.setPropertyId(propertyId);
            doc.setDocType(docType);
            doc.setFilePath(path);
            doc.setOriginalName(file.getOriginalFilename());
            propertyDocumentRepository.save(doc);

            result.put("success", true);
            result.put("documentId", doc.getId());
            result.put("docType", docType);
            result.put("originalName", doc.getOriginalName());
        } catch (IOException e) {
            result.put("success", false);
            result.put("message", "파일 업로드 중 오류가 발생했어요.");
        }

        return result;
    }
}
