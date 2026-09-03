package com.onrender.zipchatgo.property;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.MappedCollection;
import org.springframework.data.relational.core.mapping.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.Set;

@Table("member_property")
@Getter
@Setter
@NoArgsConstructor
public class MemberProperty {

    @Id
    private Long id;

    @Column("member_id")
    private Long memberId;

    @Column("property_type")
    private String propertyType; // 아파트/빌라연립/원룸투룸/단독주택/오피스텔

    @Column("deal_type")
    private String dealType; // 매매/전세/월세

    private String address1;
    private String address2;

    private Double latitude;
    private Double longitude;

    private Double area;

    @Column("floor_info")
    private String floorInfo; // 예: "12/20"

    private Integer rooms;
    private Integer baths;

    @Column("maintenance_fee")
    private Integer maintenanceFee;

    @Column("etc_fee")
    private String etcFee;

    @Column("transit_info")
    private String transitInfo; // 제출 시점 자동계산 스냅샷 (JSON 문자열)

    @Column("school_info")
    private String schoolInfo; // 제출 시점 자동계산 스냅샷 (JSON 문자열)

    private Integer price;
    private Integer deposit;
    private Integer monthly;

    @Column("owner_name")
    private String ownerName;

    @Column("owner_phone")
    private String ownerPhone;

    @Column("ownership_doc_url")
    private String ownershipDocUrl; // 소유증명 서류 (Cloudflare 연동 전까지는 비어있음)

    // PENDING(대기중) / APPROVED(승인) / REJECTED(거절)
    private String status = "PENDING";

    @Column("created_at")
    private LocalDateTime createdAt = LocalDateTime.now();

    @MappedCollection(idColumn = "property_id")
    private Set<PropertyAttribute> attributes = new HashSet<>();
}
