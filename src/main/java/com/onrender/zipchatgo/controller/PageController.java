package com.onrender.zipchatgo.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Thymeleaf 페이지 이동을 담당하는 Controller.
 *
 * templates 폴더의 HTML과 브라우저 URL을 연결한다.
 */
@Controller
public class PageController {

    @GetMapping("/")
    public String index() {
        return "index";
    }

    @GetMapping("/member/login")
    public String login() {
        return "member/login";
    }

    @GetMapping("/member/signup")
    public String signup() {
        return "member/signup";
    }

    @GetMapping("/favorite")
    public String favorite() {
        return "favorite/favorite";
    }

    @GetMapping("/support/contact")
    public String contact() {
        return "support/contact";
    }

    @GetMapping("/support/service")
    public String service() {
        return "support/Servise";
    }

    @GetMapping("/property/map")
    public String propertyMap() {
        return "property/map";
    }

    @GetMapping("/property/register")
    public String propertyRegister() {
        return "property/register";
    }

    @GetMapping("/market/trend")
    public String marketTrend() {
        return "market/trend";
    }
}
