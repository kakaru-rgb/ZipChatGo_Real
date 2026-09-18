package com.onrender.zipchatgo.map;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.servlet.view.RedirectView;

@Controller
public class MapPageController {

    // controller.PageController 에 있던 동일 템플릿 매핑(구 /property/map)은
    // 여기로 일원화하고 그쪽에서는 제거함(중복/네이밍 혼선 방지).
    @GetMapping("/property/map")
    public String map() {
        return "property/map";
    }

    @GetMapping("/templates/property/map.html")
    public RedirectView legacyMap() {
        return new RedirectView("/property/map");
    }
}
