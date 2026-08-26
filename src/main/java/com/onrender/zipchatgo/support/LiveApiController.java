package com.onrender.zipchatgo.support;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/live")
public class LiveApiController {

    @GetMapping("/recommendations")
    public List<Map<String, Object>> recommendations() {
        return List.of(
                home("성수 리버뷰 84㎡", "매매 12.8억", 37.5446, 127.0556, true, "2NpswwcViDE"),
                home("서울숲 시티뷰 59㎡", "전세 7.2억", 37.5483, 127.0447, false, "nD4g9J7o-Yc"),
                home("왕십리 파크뷰 74㎡", "매매 10.4억", 37.5385, 127.0584, false, "skvgwoCisMU"));
    }

    private Map<String, Object> home(String name, String price, double lat, double lng, boolean pick, String youtubeId) {
        return Map.of("name", name, "price", price, "lat", lat, "lng", lng, "pick", pick, "youtubeId", youtubeId);
    }
}