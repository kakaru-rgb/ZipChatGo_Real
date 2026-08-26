package com.onrender.zipchatgo.support;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.ui.Model;

@Controller
@RequestMapping("/support")
public class SupportPageController {

	@Value("${naver.maps.client-key:}")
	private String naverMapsClientKey;

	@GetMapping("/contact")
	public String contact() {
		return "support/contact";
	}

	@GetMapping("/live")
	public String live(Model model) {
		model.addAttribute("naverMapsClientKey", naverMapsClientKey);
		return "support/live";
	}
}
