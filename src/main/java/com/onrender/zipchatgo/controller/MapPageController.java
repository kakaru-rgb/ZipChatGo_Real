package com.onrender.zipchatgo.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.servlet.view.RedirectView;

@Controller
public class MapPageController {

    @GetMapping("/properties/map")
    public String map() {
        return "property/map";
    }

    @GetMapping("/templates/property/map.html")
    public RedirectView legacyMap() {
        return new RedirectView("/properties/map");
    }
}
