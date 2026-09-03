package com.onrender.zipchatgo.property;

import lombok.Getter;
import lombok.Setter;

import java.util.List;

@Getter
@Setter
public class PropertyRegisterRequest {

    private String propertyType;
    private String dealType;

    private String address1;
    private String address2;

    private Double latitude;
    private Double longitude;

    private Double area;
    private String floorInfo;
    private Integer rooms;
    private Integer baths;

    private Integer maintenanceFee;
    private String etcFee;

    private List<String> tags;
    private List<String> options;
    private List<String> utilities;

    private String transitInfo; // 프론트에서 JSON.stringify 해서 문자열로 보내줌
    private String schoolInfo;

    private Integer price;
    private Integer deposit;
    private Integer monthly;

    private String ownerName;
    private String ownerPhone;
}
