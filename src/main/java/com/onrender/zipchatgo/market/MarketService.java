package com.onrender.zipchatgo.market;

import java.io.StringReader;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

import javax.xml.parsers.DocumentBuilderFactory;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

@Service
public class MarketService {
	private static final DateTimeFormatter MONTH_FORMAT = DateTimeFormatter.ofPattern("yyyyMM");
	private static final Map<String, String> REGION_NAMES = Map.of("41117", "수원 영통구 · 광교", "41465", "용인 수지구", "41135", "성남 분당구 · 판교", "41590", "화성시 · 동탄", "11110", "서울 종로구");

	private final HttpClient httpClient = HttpClient.newHttpClient();
	private final String serviceKey;
	private final String tradeUrl;
	private final String rentUrl;
	private final String defaultRegion;

	public MarketService(@Value("${molit.service-key:}") String serviceKey,
			@Value("${molit.apt-trade-url:https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade}") String tradeUrl,
			@Value("${molit.apt-rent-url:https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent}") String rentUrl,
			@Value("${molit.default-region:41117}") String defaultRegion) {
		this.serviceKey = serviceKey;
		this.tradeUrl = tradeUrl;
		this.rentUrl = rentUrl;
		this.defaultRegion = defaultRegion;
	}

	public Map<String, Object> health() {
		return map("ok", true, "service", "jipchatgo-market-api", "source", hasServiceKey() ? "molit-openapi" : "demo");
	}

	public Map<String, Object> summary(String region, String month) {
		String lawdCode = region == null || region.isBlank() ? defaultRegion : region.trim();
		String dealMonth = month == null || month.isBlank() ? previousMonth() : month.trim();
		if (!lawdCode.matches("\\d{5}")) return map("ok", false, "message", "region은 법정동코드 앞 5자리여야 합니다. 예: 41117");
		if (!dealMonth.matches("\\d{6}")) return map("ok", false, "message", "month는 YYYYMM 형식이어야 합니다. 예: 202606");
		if (!hasServiceKey()) return demo(lawdCode, dealMonth);
		try {
			String previous = previousMonth(dealMonth);
			List<Map<String, String>> tradeNow = call(tradeUrl, lawdCode, dealMonth);
			List<Map<String, String>> tradePrevious = call(tradeUrl, lawdCode, previous);
			List<Map<String, String>> rentNow = call(rentUrl, lawdCode, dealMonth);
			List<Map<String, String>> rentPrevious = call(rentUrl, lawdCode, previous);
			return buildSummary(lawdCode, dealMonth, previous, tradeNow, tradePrevious, rentNow, rentPrevious);
		} catch (Exception exception) {
			return map("ok", false, "message", "시장동향 데이터를 불러오는 중 오류가 발생했습니다.", "detail", exception.getMessage());
		}
	}

	private List<Map<String, String>> call(String baseUrl, String region, String month) throws Exception {
		String url = baseUrl + "?serviceKey=" + URLEncoder.encode(serviceKey, StandardCharsets.UTF_8) + "&LAWD_CD=" + region + "&DEAL_YMD=" + month + "&pageNo=1&numOfRows=1000";
		HttpRequest request = HttpRequest.newBuilder(URI.create(url)).header("Accept", "application/xml,text/xml,*/*").build();
		String xml = httpClient.send(request, HttpResponse.BodyHandlers.ofString()).body();
		var document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(new InputSource(new StringReader(xml)));
		NodeList nodes = document.getElementsByTagName("item");
		List<Map<String, String>> result = new ArrayList<>();
		for (int index = 0; index < nodes.getLength(); index++) {
			NodeList fields = nodes.item(index).getChildNodes();
			Map<String, String> item = new HashMap<>();
			for (int fieldIndex = 0; fieldIndex < fields.getLength(); fieldIndex++) {
				Node field = fields.item(fieldIndex);
				if (field.getNodeType() == Node.ELEMENT_NODE) item.put(field.getNodeName(), field.getTextContent().trim());
			}
			result.add(item);
		}
		return result;
	}

	private Map<String, Object> buildSummary(String region, String month, String previous, List<Map<String, String>> tradeNow, List<Map<String, String>> tradePrevious, List<Map<String, String>> rentNow, List<Map<String, String>> rentPrevious) {
		double saleAverage = average(tradeNow, item -> number(first(item, "dealAmount", "dealAmt", "거래금액")));
		double previousSaleAverage = average(tradePrevious, item -> number(first(item, "dealAmount", "dealAmt", "거래금액")));
		double rentAverage = average(rentNow, item -> number(first(item, "deposit", "보증금액")));
		double previousRentAverage = average(rentPrevious, item -> number(first(item, "deposit", "보증금액")));
		double saleRate = changeRate(saleAverage, previousSaleAverage), rentRate = changeRate(rentAverage, previousRentAverage), volumeRate = changeRate(tradeNow.size(), tradePrevious.size());
		String saleStatus = status(saleRate), rentStatus = status(rentRate), volumeStatus = volumeStatus(volumeRate);
		String hotRegion = tradeNow.stream().map(item -> first(item, "umdNm", "법정동")).filter(Objects::nonNull).collect(Collectors.groupingBy(Function.identity(), Collectors.counting())).entrySet().stream().max(Map.Entry.comparingByValue()).map(Map.Entry::getKey).orElse(REGION_NAMES.getOrDefault(region, "관심지역"));
		return map("ok", true, "source", "molit-openapi", "regionCode", region, "regionName", REGION_NAMES.getOrDefault(region, region + " 지역"), "dealYmd", month, "prevYmd", previous, "saleStatus", saleStatus, "jeonseStatus", rentStatus, "volumeStatus", volumeStatus, "hotRegion", hotRegion, "saleAvg", saleAverage, "saleChangeRate", saleRate, "jeonseAvgDeposit", rentAverage, "jeonseChangeRate", rentRate, "tradeCount", tradeNow.size(), "tradeCountPrev", tradePrevious.size(), "volumeChangeRate", volumeRate, "sampleTradeList", tradeNow.stream().limit(50).map(this::normalizeTrade).toList(), "sampleRentList", rentNow.stream().limit(50).map(this::normalizeRent).toList(), "saleText", "매매가격은 전월 대비 " + rateText(saleRate) + " 수준으로 " + saleStatus + " 흐름입니다.", "jeonseText", "전세 보증금 흐름은 전월 대비 " + rateText(rentRate) + " 수준으로 " + rentStatus + "입니다.", "volumeText", "거래량은 전월 " + tradePrevious.size() + "건에서 현재 " + tradeNow.size() + "건으로 " + rateText(volumeRate) + " 변해 " + volumeStatus + " 분위기입니다.", "aiText", "현재 시장은 매매 " + saleStatus + ", 전세 " + rentStatus + ", 거래량 " + volumeStatus + " 흐름입니다.");
	}

	private Map<String, Object> demo(String region, String month) { return map("ok", true, "source", "demo", "regionCode", region, "regionName", REGION_NAMES.getOrDefault(region, region + " 지역"), "dealYmd", month, "prevYmd", previousMonth(month), "saleStatus", "보합세", "jeonseStatus", "수요 증가", "volumeStatus", "관망세", "hotRegion", "광교 · 판교", "saleAvg", 87200, "saleChangeRate", 0.7, "jeonseAvgDeposit", 51200, "jeonseChangeRate", 2.1, "tradeCount", 42, "tradeCountPrev", 39, "volumeChangeRate", 7.7, "rentCount", 1, "rentCountPrev", 1, "rentVolumeChangeRate", 0, "sampleTradeList", List.of(), "sampleRentList", List.of(), "saleText", "실제 API 키를 넣으면 국토교통부 실거래가 기준으로 매매 흐름을 자동 계산합니다.", "jeonseText", "실제 API 키를 넣으면 국토교통부 실거래 데이터를 기준으로 전세 흐름을 자동 계산합니다.", "volumeText", "실제 API 키를 넣으면 전월 대비 거래량 변화를 자동 계산합니다.", "aiText", "현재는 데모 데이터입니다. API 키 입력 후 실제 시장 데이터를 기준으로 자동 분석됩니다."); }
	private Map<String, Object> normalizeTrade(Map<String, String> item) { return map("aptName", first(item, "aptNm", "아파트"), "dong", first(item, "umdNm", "법정동"), "amount", number(first(item, "dealAmount", "dealAmt", "거래금액")), "area", first(item, "excluUseAr", "exclUseAr", "전용면적"), "floor", first(item, "floor", "층"), "day", first(item, "dealDay", "계약일")); }
	private Map<String, Object> normalizeRent(Map<String, String> item) { return map("aptName", first(item, "aptNm", "아파트"), "dong", first(item, "umdNm", "법정동"), "deposit", number(first(item, "deposit", "보증금액")), "monthlyRent", number(first(item, "monthlyRent", "월세금액")), "area", first(item, "excluUseAr", "exclUseAr", "전용면적"), "floor", first(item, "floor", "층"), "day", first(item, "dealDay", "계약일")); }
	private static String first(Map<String, String> item, String... keys) { for (String key : keys) if (item.get(key) != null && !item.get(key).isBlank()) return item.get(key); return "-"; }
	private static double number(String value) { try { return Double.parseDouble(value.replace(",", "").trim()); } catch (Exception exception) { return 0; } }
	private static double average(List<Map<String, String>> items, Function<Map<String, String>, Double> mapper) { return Math.round(items.stream().map(mapper).filter(value -> value > 0).mapToDouble(Double::doubleValue).average().orElse(0)); }
	private static double changeRate(double now, double previous) { return previous == 0 || now == 0 ? 0 : Math.round(((now - previous) / previous) * 1000) / 10.0; }
	private static String status(double rate) { return rate >= 2 ? "상승세" : rate <= -2 ? "하락세" : "보합세"; }
	private static String volumeStatus(double rate) { return rate >= 15 ? "거래 회복" : rate <= -15 ? "거래 감소" : "관망세"; }
	private static String rateText(double rate) { return (rate > 0 ? "+" : "") + rate + "%"; }
	private static String previousMonth() { return YearMonth.now().minusMonths(1).format(MONTH_FORMAT); }
	private static String previousMonth(String month) { return YearMonth.parse(month, MONTH_FORMAT).minusMonths(1).format(MONTH_FORMAT); }
	private boolean hasServiceKey() { return serviceKey != null && !serviceKey.isBlank() && !serviceKey.contains("여기에") && !serviceKey.contains("YOUR_"); }
	private static Map<String, Object> map(Object... values) { Map<String, Object> result = new LinkedHashMap<>(); for (int index = 0; index < values.length; index += 2) result.put((String) values[index], values[index + 1]); return result; }
}