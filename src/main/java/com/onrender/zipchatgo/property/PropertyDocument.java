package com.onrender.zipchatgo.property;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

@Table("property_document")
@Getter
@Setter
@NoArgsConstructor
public class PropertyDocument {

    @Id
    private Long id;

    @Column("property_id")
    private Long propertyId;

    // OWNERSHIP(등기부등본) / BUILDING_REGISTER(건축물대장) / LAND_REGISTER(토지대장)
    @Column("doc_type")
    private String docType;

    // Supabase Storage 안에서의 object 경로. 실제 파일 자체는 여기 저장 안 함.
    @Column("file_path")
    private String filePath;

    @Column("original_name")
    private String originalName;

    @Column("uploaded_at")
    private LocalDateTime uploadedAt = LocalDateTime.now();
}
