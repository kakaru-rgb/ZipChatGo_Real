package com.onrender.zipchatgo.property;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * Supabase Storage REST API를 RestTemplate로 직접 호출한다.
 * (전용 SDK 없이도 REST API만으로 업로드/서명URL 발급이 가능해서 별도 의존성 추가 없이 구현)
 */
@Service
public class SupabaseStorageService {

    @Value("${supabase.url:}")
    private String supabaseUrl;

    @Value("${supabase.service-key:}")
    private String serviceKey;

    @Value("${supabase.bucket:}")
    private String bucket;

    private final RestTemplate restTemplate = new RestTemplate();

    /**
     * 파일을 버킷의 지정된 경로에 업로드한다.
     */
    public void upload(String path, byte[] content, String contentType) {
        String uploadUrl = supabaseUrl + "/storage/v1/object/" + bucket + "/" + path;

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + serviceKey);
        headers.setContentType(
                contentType != null ? MediaType.parseMediaType(contentType) : MediaType.APPLICATION_OCTET_STREAM
        );

        HttpEntity<byte[]> entity = new HttpEntity<>(content, headers);
        restTemplate.exchange(uploadUrl, HttpMethod.POST, entity, String.class);
    }

    /**
     * 비공개 버킷의 파일을 잠깐(기본 10분) 열람할 수 있는 서명된 URL을 발급한다.
     */
    public String createSignedUrl(String path, int expiresInSeconds) {
        String signUrl = supabaseUrl + "/storage/v1/object/sign/" + bucket + "/" + path;

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + serviceKey);
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> body = new HashMap<>();
        body.put("expiresIn", expiresInSeconds);

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<Map> response = restTemplate.exchange(signUrl, HttpMethod.POST, entity, Map.class);
            Object signedPath = response.getBody() != null ? response.getBody().get("signedURL") : null;
            return signedPath != null ? supabaseUrl + "/storage/v1" + signedPath : null;
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * 버킷에서 여러 파일을 한번에 삭제한다. 매물 삭제 시 첨부된 서류/사진 파일을 같이 지우는 용도.
     * 실패해도 예외를 던지지 않는다 (파일 삭제가 실패해도 DB 정리는 계속 진행되어야 해서).
     */
    public void deleteObjects(java.util.List<String> paths) {
        if (paths == null || paths.isEmpty()) return;

        String deleteUrl = supabaseUrl + "/storage/v1/object/" + bucket;

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + serviceKey);
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> body = new HashMap<>();
        body.put("prefixes", paths);

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        try {
            restTemplate.exchange(deleteUrl, HttpMethod.DELETE, entity, String.class);
        } catch (Exception e) {
            // 파일 삭제가 실패해도 DB 쪽 정리는 계속 진행 (고아 파일이 남더라도 DB는 깨끗해야 함)
        }
    }
}
