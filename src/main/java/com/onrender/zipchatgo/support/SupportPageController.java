package com.onrender.zipchatgo.support;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class SupportPageController {

	@GetMapping("/support/contact")
	public String contact() {
		return "support/contact";
	}
}
