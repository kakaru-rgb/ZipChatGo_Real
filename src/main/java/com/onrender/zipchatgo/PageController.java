package com.onrender.zipchatgo;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class PageController {

	@GetMapping({"/", "/index.html"})
	public String index() {
		return "index";
	}

	@GetMapping("/market/trend")
	public String marketTrend() {
		return "market/trend";
	}
}