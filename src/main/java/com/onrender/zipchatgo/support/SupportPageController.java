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

    @GetMapping("/support/service")
    public String supportService() {
        return "support/service";
    }

    // /about 경로 별칭
    @GetMapping("/about/service")
    public String aboutService() {
        return "support/service";
    }

    @GetMapping("/about/team")
    public String aboutTeam() {
        return "support/team";
    }

    // /content 경로 별칭
    @GetMapping("/content/modelhouse")
    public String contentModelhouse() {
        return "support/modelhouse";
    }
}
