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

	@GetMapping({"/about/service", "/support/service"})
	public String service() {
		return "support/service";
	}

	@GetMapping("/about/team")
	public String team() {
		return "support/team";
	}

	@GetMapping("/support/guide")
	public String guide() {
		return "support/guide";
	}

	@GetMapping("/login")
	public String login() {
		return "member/login";
	}

	@GetMapping("/join")
	public String signup() {
		return "member/signup";
	}

	@GetMapping("/content/modelhouse")
	public String modelhouse() {
		return "support/modelhouse";
	}

	@GetMapping("/properties/register")
	public String propertyRegister() {
		return "property/register";
	}
}