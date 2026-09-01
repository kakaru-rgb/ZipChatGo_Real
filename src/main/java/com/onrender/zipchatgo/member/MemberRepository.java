package com.onrender.zipchatgo.member;

import org.springframework.data.jdbc.repository.query.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface MemberRepository extends CrudRepository<Member, Long> {

    @Query("SELECT * FROM member WHERE email = :email")
    Optional<Member> findByEmail(@Param("email") String email);

    @Query("SELECT COUNT(*) > 0 FROM member WHERE email = :email")
    boolean existsByEmail(@Param("email") String email);
}
