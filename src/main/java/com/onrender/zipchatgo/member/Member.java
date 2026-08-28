package com.onrender.zipchatgo.member;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Table("member")
@Getter
@Setter
@NoArgsConstructor
public class Member {

    @Id
    private Long id;

    private String email;

    private String password; // BCrypt로 암호화되어 저장됨

    private String name;

    private String phone;

    // "GENERAL"(일반회원) / "BROKER"(공인중개사) - 이번 작업은 GENERAL만 실제 사용
    @Column("member_type")
    private String memberType = "GENERAL";

    // 공인중개사 관련 필드 (일반회원은 null)
    @Column("broker_shop")
    private String brokerShop;

    @Column("broker_biz_no")
    private String brokerBizNo;

    @Column("broker_license")
    private String brokerLicense;
}
