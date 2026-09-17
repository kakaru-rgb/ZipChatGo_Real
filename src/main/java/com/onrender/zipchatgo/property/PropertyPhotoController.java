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
@RequestMapping("/api/properties/{propertyId}/photos")
@RequiredArgsConstructor
public class PropertyPhotoController {

    private static final String SESSION_KEY = "loginMemberId";

    private final PropertyPhotoRepository propertyPhotoRepository;
    private final MemberPropertyRepository memberPropertyRepository;
    private final SupabaseStorageService supabaseStorageService;

    // 사진 한 장씩 업로드 (프론트에서 여러 장이면 이 API를 반복 호출)
    @PostMapping
    public Map<String, Object> upload(@PathVariable Long propertyId,
                                       @RequestParam("file") MultipartFile file,
                                       @RequestParam(value = "sortOrder", defaultValue = "0") Integer sortOrder,
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
            result.put("message", "본인이 등록한 매물에만 사진을 첨부할 수 있어요.");
            return result;
        }

        try {
            String safeName = file.getOriginalFilename() != null
                    ? file.getOriginalFilename().replaceAll("[^a-zA-Z0-9._-]", "_")
                    : "photo";
            String path = propertyId + "/photos/" + System.currentTimeMillis() + "_" + safeName;

            supabaseStorageService.upload(path, file.getBytes(), file.getContentType());

            PropertyPhoto photo = new PropertyPhoto();
            photo.setPropertyId(propertyId);
            photo.setFilePath(path);
            photo.setOriginalName(file.getOriginalFilename());
            photo.setSortOrder(sortOrder);
            propertyPhotoRepository.save(photo);

            result.put("success", true);
            result.put("photoId", photo.getId());
        } catch (IOException e) {
            result.put("success", false);
            result.put("message", "사진 업로드 중 오류가 발생했어요.");
        }

        return result;
    }
}
