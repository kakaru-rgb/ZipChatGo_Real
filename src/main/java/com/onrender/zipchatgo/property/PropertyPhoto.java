package com.onrender.zipchatgo.property;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

@Table("property_photo")
@Getter
@Setter
@NoArgsConstructor
public class PropertyPhoto {

    @Id
    private Long id;

    @Column("property_id")
    private Long propertyId;

    @Column("file_path")
    private String filePath;

    @Column("original_name")
    private String originalName;

    @Column("sort_order")
    private Integer sortOrder = 0;

    @Column("uploaded_at")
    private LocalDateTime uploadedAt = LocalDateTime.now();
}
