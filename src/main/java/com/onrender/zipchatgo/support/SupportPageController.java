package com.onrender.zipchatgo.support;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * templates/support/*.html 라우팅을 전담.
 * controller.PageController 에 있던 /support/contact, /support/service 는
 * 여기로 이관되었으므로 그쪽에서는 삭제할 것(중복 매핑 방지).
 */
@Controller
public class SupportPageController {

    @GetMapping("/support/contact")
    public String contact() {
        return "support/contact";
    }

    @GetMapping("/support/guide")
    public String guide() {
        return "support/guide";
    }

    @GetMapping("/support/live")
    public String live() {
        return "support/live";
    }

    @GetMapping("/support/modelhouse")
    public String modelhouse() {
        return "support/modelhouse";
    }

    @GetMapping("/support/notice")
    public String notice() {
        return "support/notice";
    }

    @GetMapping("/support/team")
    public String team() {
        return "support/team";
    }

    // 실제 템플릿 파일명이 Servise.html(오타)이라 리턴값을 맞춤.
    // 가능하면 파일명을 service.html로 정정하는 것을 권장.
    @GetMapping("/support/service")
    public String service() {
        return "support/Servise";
    }
}
