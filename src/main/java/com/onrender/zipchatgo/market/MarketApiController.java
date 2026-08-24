package com.onrender.zipchatgo.market;

import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/market")
public class MarketApiController {
	private final MarketService marketService;

	public MarketApiController(MarketService marketService) {
		this.marketService = marketService;
	}

	@GetMapping("/health")
	public Map<String, Object> health() {
		return marketService.health();
	}

	@GetMapping("/summary")
	public Map<String, Object> summary(@RequestParam(required = false) String region,
			@RequestParam(required = false) String month) {
		return marketService.summary(region, month);
	}
}