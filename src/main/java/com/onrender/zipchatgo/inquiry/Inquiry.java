package com.onrender.zipchatgo.inquiry;

import java.time.LocalDateTime;

import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("inquiry")
public class Inquiry {

	@Id
	private Long id;
	@Column("member_id")
	private final Long memberId;
	private final String name;
	private final String email;
	private final String type;
	private final String title;
	private final String message;
	private final String status;
	@Column("created_at")
	private final LocalDateTime createdAt;

	public Inquiry(Long id, Long memberId, String name, String email, String type,
			String title, String message, String status, LocalDateTime createdAt) {
		this.id = id;
		this.memberId = memberId;
		this.name = name;
		this.email = email;
		this.type = type;
		this.title = title;
		this.message = message;
		this.status = status;
		this.createdAt = createdAt;
	}

	public Long getId() { return id; }
	public Long getMemberId() { return memberId; }
	public String getName() { return name; }
	public String getEmail() { return email; }
	public String getType() { return type; }
	public String getTitle() { return title; }
	public String getMessage() { return message; }
	public String getStatus() { return status; }
	public LocalDateTime getCreatedAt() { return createdAt; }
}
