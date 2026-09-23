package com.onrender.zipchatgo.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.servlet.view.RedirectView;

@Controller
public class FavoritePageController {

    @GetMapping("/favorites")
    public String favorites() {
        return "favorite/favorite";
    }

    @GetMapping({"/favorite", "/templates/favorite/favorite.html"})
    public RedirectView legacyFavorites() {
        return new RedirectView("/favorites");
    }
}
