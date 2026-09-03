package com.onrender.zipchatgo.property;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Table;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Table("property_attribute")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class PropertyAttribute {

    @Id
    private Long id;

    // TAG(특징) / OPTION(옵션) / UTILITY(관리비 포함 사용료)
    private String category;

    private String value;
}
